import json
import os
import sys
import threading
import time
import uuid
import socket
import csv
import io

from flask import Flask, jsonify, request, send_file, render_template_string
from werkzeug.utils import secure_filename
from flask_cors import CORS
from mido import Message, get_input_names, get_output_names, open_input, open_output
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import ThreadingOSCUDPServer

# --- Configuration Management ---
CONFIG_FILE = "config.json"
config = {}


def load_config():
    """Loads configuration from JSON file or creates a default one."""
    global config
    try:
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
    except FileNotFoundError:
        print(f"WARNING: {CONFIG_FILE} not found. Creating a default config.")
        config = {
            "osc_server_ip": "0.0.0.0",
            "osc_server_port": 9000,
            "rtp_midi_target_ip": "192.168.1.100",
            "rtp_midi_target_port": 5004,
            "midi_input_name": None,
            "midi_output_name": None,
            "song_parser_settings": {
                "column_name": "QUAD PATCH",
                "scene_prefix": "SC ",
                "footswitch_prefix": "FS ",
                "osc_prefix": "/patch"
            },
            "osc_mappings": [],
        }
        save_config()

def save_config():
    """Saves the current configuration to the JSON file."""
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)

def parse_song_csv(file_stream, song_title, setlist_number, settings):
    """Parses a song CSV and generates a list of OSC mappings."""
    generated_mappings = []
    last_value = None
    
    # Decode the file stream and read it using DictReader
    # This allows accessing columns by header name
    try:
        # Use io.TextIOWrapper to properly handle text encoding from the byte stream
        csv_file = io.TextIOWrapper(file_stream, encoding='utf-8')
        reader = csv.DictReader(csv_file)
        
        # Check if the specified column exists
        if settings['column_name'] not in reader.fieldnames:
            raise ValueError(f"Column '{settings['column_name']}' not found in CSV.")

        temp_mappings = []

        for row in reader:
            value = row.get(settings['column_name'], "").strip()

            # Skip empty rows or if the value is the same as the last one
            if not value or value == last_value:
                continue
            
            last_value = value
            midi_sequence = []
            description = ""
            channel = 1

            try:
                # --- Footswitch Logic ---
                if value.startswith(settings['footswitch_prefix']):
                    fs_char = value.replace(settings['footswitch_prefix'], '').strip().upper()
                    if 'A' <= fs_char <= 'H':
                        control = 35 + (ord(fs_char) - ord('A'))
                        description = f"QC: Toggle Footswitch {fs_char}"
                        midi_sequence = [{"type": "control_change", "channel": channel, "control": control, "value": 127}]
                    else: continue # Skip invalid footswitch letters

                # --- Scene Logic ---
                elif value.startswith(settings['scene_prefix']):
                    sc_char = value.replace(settings['scene_prefix'], '').strip().upper()
                    if 'A' <= sc_char <= 'H':
                        scene_val = ord(sc_char) - ord('A')
                        description = f"QC: Select Scene {sc_char}"
                        midi_sequence = [{"type": "control_change", "channel": channel, "control": 43, "value": scene_val}]
                    else: continue # Skip invalid scene letters

                # --- Patch Change Logic ---
                else:
                    patch_num_str = ''.join(filter(str.isdigit, value))
                    patch_char = ''.join(filter(str.isalpha, value)).upper()
                    
                    if patch_num_str and 'A' <= patch_char <= 'H':
                        patch_num = int(patch_num_str)
                        patch_letter_val = ord(patch_char) - ord('A')
                        
                        preset_index = (patch_num - 1) * 8 + patch_letter_val
                        bank = 1 if preset_index > 127 else 0
                        program = preset_index % 128
                        
                        description = f"QC: Setlist {setlist_number + 1}, Patch {patch_num}{patch_char}"
                        midi_sequence = [
                            {"type": "control_change", "channel": channel, "control": 0, "value": bank},
                            {"type": "control_change", "channel": channel, "control": 32, "value": setlist_number},
                            {"type": "program_change", "channel": channel, "program": program}
                        ]
                    else: continue # Skip invalid patch formats

                if midi_sequence:
                    temp_mappings.append({"description": description, "midi_sequence": midi_sequence})

            except Exception as e:
                print(f"Warning: Could not parse row value '{value}'. Error: {e}")
                continue
        
        # Second pass to create final mappings with correct OSC addresses
        total_mappings = len(temp_mappings)
        sanitized_title = song_title.lower().replace(' ', '_').replace('/', '_')
        
        for i, temp_map in enumerate(temp_mappings):
            osc_address = f"{settings['osc_prefix']}/{sanitized_title}/{i+1}"
            final_map = {
                "id": uuid.uuid4().hex,
                "osc_address": osc_address,
                "description": temp_map['description'],
                "midi_sequence": temp_map['midi_sequence']
            }
            generated_mappings.append(final_map)

    except Exception as e:
        # This will catch file reading errors, decoding errors, or the column not found error
        raise e

    return generated_mappings


# --- Global Variables for Core Logic ---
midi_in_port = None
midi_out_port = None
rtp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
rtp_sequence_number = 0
rtp_ssrc = int(time.time())  # A unique identifier for this RTP stream


# --- Core Logic: OSC to MIDI ---
def osc_handler(address, *args):
    """Handles incoming OSC messages and translates them to a MIDI sequence."""
    global midi_out_port
    print(f"OSC Received: {address} {args}")

    if not midi_out_port:
        print("Warning: MIDI output port not configured or open.")
        return

    for mapping in config.get("osc_mappings", []):
        if mapping["osc_address"] == address:
            # NEW: Check for midi_sequence
            midi_sequence = mapping.get("midi_sequence", [])
            if not midi_sequence:
                continue

            print(f"Found mapping for {address}. Sending sequence...")
            for midi_info in midi_sequence:
                try:
                    msg_type = midi_info["type"]
                    channel = int(midi_info["channel"]) - 1  # Mido is 0-indexed

                    if msg_type == "program_change":
                        msg = Message(
                            "program_change",
                            channel=channel,
                            program=int(midi_info["program"]),
                        )
                    elif msg_type == "control_change":
                        msg = Message(
                            "control_change",
                            channel=channel,
                            control=int(midi_info["control"]),
                            value=int(midi_info["value"]),
                        )
                    else:
                        print(f"Unsupported MIDI message type: {msg_type}")
                        continue

                    print(f"  -> Sending MIDI: {msg}")
                    midi_out_port.send(msg)
                    time.sleep(0.01) # Small delay between messages can improve reliability

                except Exception as e:
                    print(f"Error processing step in sequence for {address}: {e}")

# --- Core Logic: MIDI to RTP-MIDI ---
def send_rtp_midi(midi_message):
    """Packages and sends a Mido message as an RTP-MIDI packet."""
    global rtp_sequence_number
    if not config.get("rtp_midi_target_ip"):
        return

    # RTP Header (12 bytes)
    header = bytearray(12)
    header[0] = 0x80  # Version 2, no padding, no extension
    header[1] = 0x61  # Payload Type 97 (dynamic)
    header[2:4] = rtp_sequence_number.to_bytes(2, "big")
    timestamp = int(time.time() * 1000) & 0xFFFFFFFF
    header[4:8] = timestamp.to_bytes(4, "big")
    header[8:12] = rtp_ssrc.to_bytes(4, "big")

    # MIDI Command Section (variable length)
    # For simplicity, we send one MIDI message per packet
    midi_command = bytearray()
    midi_command.append(0x00)  # Delta time (B-bit set to 0)
    midi_command.extend(midi_message.bin())

    packet = header + midi_command
    target = (
        config["rtp_midi_target_ip"],
        config["rtp_midi_target_port"],
    )
    rtp_socket.sendto(packet, target)
    rtp_sequence_number = (rtp_sequence_number + 1) & 0xFFFF


def midi_input_thread_func():
    """Thread that listens for MIDI input and sends it via RTP-MIDI."""
    global midi_in_port
    print("Starting MIDI input listener...")
    while True:
        if midi_in_port:
            for msg in midi_in_port.iter_pending():
                print(f"MIDI In: {msg} -> Sending via RTP-MIDI")
                send_rtp_midi(msg)
        time.sleep(0.001)  # Prevent busy-waiting


# --- Flask API Setup ---
app = Flask(__name__)
CORS(app)  # Allow cross-origin requests for your frontend

ADMIN_PAGE_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>StageBridge Network Admin</title>
    <style>
        body { font-family: sans-serif; background-color: #1a1a1a; color: #e0e0e0; margin: 40px; }
        .container { max-width: 600px; margin: auto; background-color: #2b2b2b; padding: 20px; border-radius: 8px; }
        h1, h2 { border-bottom: 1px solid #444; padding-bottom: 10px; }
        .form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 20px; }
        label { font-weight: bold; }
        input { width: 100%; padding: 8px; background-color: #333; color: #e0e0e0; border: 1px solid #444; border-radius: 4px; box-sizing: border-box; }
        input[readonly] { background-color: #444; cursor: not-allowed; }
        button { background-color: #dc3545; color: white; border: none; padding: 12px 20px; border-radius: 5px; cursor: pointer; font-size: 1em; }
        .warning { color: #ffc107; margin-top: 20px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Network Admin</h1>
        <p>Configure core network settings. Changes require a service restart.</p>
        <form method="POST">
            <h2>OSC Server (Incoming)</h2>
            <div class="form-grid">
                <div>
                    <label for="osc_server_ip">Listen IP Address</label>
                    <input type="text" id="osc_server_ip" name="osc_server_ip" value="{{ config.osc_server_ip }}" readonly>
                </div>
                <div>
                    <label for="osc_server_port">Listen Port</label>
                    <input type="number" id="osc_server_port" name="osc_server_port" value="{{ config.osc_server_port }}" required>
                </div>
            </div>

            <h2>RTP-MIDI (Outgoing)</h2>
            <div class="form-grid">
                <div>
                    <label for="rtp_midi_target_ip">Target IP Address</label>
                    <input type="text" id="rtp_midi_target_ip" name="rtp_midi_target_ip" value="{{ config.rtp_midi_target_ip }}" required>
                </div>
                <div>
                    <label for="rtp_midi_target_port">Target Port</label>
                    <input type="number" id="rtp_midi_target_port" name="rtp_midi_target_port" value="{{ config.rtp_midi_target_port }}" required>
                </div>
            </div>
            <button type="submit">Save & Restart Service</button>
            <p class="warning"><strong>Warning:</strong> Saving will immediately restart the entire StageBridge service.</p>
        </form>
    </div>
</body>
</html>
"""

def trigger_restart():
    """Contains the logic to exit the script for systemd to restart."""
    def do_exit():
        time.sleep(1)
        sys.exit(0)
    
    exit_thread = threading.Thread(target=do_exit)
    exit_thread.daemon = True
    exit_thread.start()

@app.route("/api/status", methods=["GET"])
def get_status():
    return jsonify(
        {
            "service": "OSC-MIDI StageBridge",
            "status": "running",
            "midi_input": midi_in_port.name if midi_in_port else "Not Connected",
            "midi_output": midi_out_port.name if midi_out_port else "Not Connected",
        }
    )


@app.route("/api/midi-ports", methods=["GET"])
def get_midi_ports_api():
    return jsonify(
        {"inputs": get_input_names(), "outputs": get_output_names()}
    )


@app.route("/api/config", methods=["GET", "PUT"])
def manage_config():
    if request.method == "GET":
        return jsonify(config)
    elif request.method == "PUT":
        new_config = request.json
        # Basic validation could be added here
        config.clear()
        config.update(new_config)
        save_config()
        # NOTE: In a production app, you'd restart threads here
        return jsonify({"message": "Config updated. Restart script to apply changes."})
    
@app.route("/api/config/download", methods=["GET"])
def download_config():
    """Provides the config.json file for download."""
    try:
        return send_file(
            CONFIG_FILE, as_attachment=True, download_name="config.json"
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/config/upload", methods=["POST"])
def upload_config():
    """Receives a new config.json, validates it, and overwrites the old one."""
    if "file" not in request.files:
        return jsonify({"error": "No file part in the request"}), 400
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    if file and file.filename.endswith(".json"):
        # Secure the filename before using it
        filename = secure_filename(file.filename)
        try:
            # First, try to load the file to validate its JSON content
            new_config_data = json.load(file)
            # If validation passes, save the file
            # We need to re-open the file or seek to the beginning
            file.seek(0)
            with open(CONFIG_FILE, "w") as f:
                json.dump(new_config_data, f, indent=2)

            # Reload the configuration into the running application
            load_config()
            return jsonify(
                {
                    "message": "Configuration uploaded successfully. "
                    "Please restart the script if MIDI ports were changed."
                }
            )
        except json.JSONDecodeError:
            return jsonify({"error": "Invalid JSON format in uploaded file"}), 400
        except Exception as e:
            return jsonify({"error": f"An error occurred: {str(e)}"}), 500
    else:
        return jsonify({"error": "Invalid file type, please upload a .json file"}), 400

@app.route("/api/songs/upload", methods=["POST"])
def upload_song_csv():
    """Receives a song CSV and generates mappings."""
    if "file" not in request.files:
        return jsonify({"error": "No file part in the request"}), 400
    
    file = request.files["file"]
    song_title = request.form.get("song_title")
    setlist_number_str = request.form.get("setlist_number")

    if not all([file, song_title, setlist_number_str]):
        return jsonify({"error": "Missing form data (file, song_title, or setlist_number)"}), 400

    try:
        setlist_number = int(setlist_number_str) - 1 # Convert to 0-indexed
        parser_settings = config.get("song_parser_settings", {})
        
        new_mappings = parse_song_csv(file.stream, song_title, setlist_number, parser_settings)
        
        if not new_mappings:
            return jsonify({"message": "No new mappings were generated. The values might be duplicates or the column is empty."}), 200

        config["osc_mappings"].extend(new_mappings)
        save_config()
        
        return jsonify({"message": f"Successfully added {len(new_mappings)} mappings for '{song_title}'."})

    except ValueError as e:
        return jsonify({"error": f"Invalid input: {e}"}), 400
    except Exception as e:
        return jsonify({"error": f"An error occurred during parsing: {e}"}), 500

@app.route("/api/mappings", methods=["POST"])
def add_mapping():
    mapping = request.json
    mapping["id"] = uuid.uuid4().hex
    config["osc_mappings"].append(mapping)
    save_config()
    return jsonify(mapping), 201


@app.route("/api/mappings/<mapping_id>", methods=["PUT", "DELETE"])
def manage_mapping(mapping_id):
    mappings = config["osc_mappings"]
    mapping_found = next((m for m in mappings if m["id"] == mapping_id), None)

    if not mapping_found:
        return jsonify({"error": "Mapping not found"}), 404

    if request.method == "PUT":
        update_data = request.json
        mapping_found.update(update_data)
        save_config()
        return jsonify(mapping_found)

    elif request.method == "DELETE":
        config["osc_mappings"] = [
            m for m in mappings if m["id"] != mapping_id
        ]
        save_config()
        return jsonify({"message": "Mapping deleted"}), 200
    
@app.route("/api/system/restart", methods=["POST"])
def system_restart():
    """Exits the script, relying on systemd to restart it."""
    print("INFO: Received restart command from main UI.")
    trigger_restart()
    return jsonify({"message": "Server is restarting..."})

@app.route("/admin", methods=["GET", "POST"])
def admin_page():
    if request.method == "POST":
        print("INFO: Received new network config from Admin Page.")
        # Update config from form
        config["osc_server_port"] = int(request.form["osc_server_port"])
        config["rtp_midi_target_ip"] = request.form["rtp_midi_target_ip"]
        config["rtp_midi_target_port"] = int(request.form["rtp_midi_target_port"])
        
        save_config()
        
        # Trigger the restart
        trigger_restart()
        
        return "<h1>Configuration saved. Restarting service...</h1>"

    # For GET request, render the page
    return render_template_string(ADMIN_PAGE_TEMPLATE, config=config)



# --- Main Execution ---
if __name__ == "__main__":
    load_config()
    
    print("\n--- Detected MIDI Devices ---")
    try:
        input_ports = get_input_names()
        output_ports = get_output_names()
        print(f"Available MIDI Inputs: {input_ports}")
        print(f"Available MIDI Outputs: {output_ports}")
        if not input_ports and not output_ports:
            print("No MIDI devices detected. Make sure your USB-MIDI interface is connected.")
    except Exception as e:
        print(f"Error detecting MIDI devices: {e}")
    print("---------------------------\n")

    # Initialize MIDI Ports
    try:
        if config.get("midi_input_name"):
            midi_in_port = open_input(config["midi_input_name"])
        if config.get("midi_output_name"):
            midi_out_port = open_output(config["midi_output_name"])
    except Exception as e:
        print(f"Error opening MIDI ports: {e}")
        print("Please configure MIDI ports via the API and restart.")

    # Start MIDI Input Listener Thread
    midi_thread = threading.Thread(target=midi_input_thread_func, daemon=True)
    midi_thread.start()

    # Setup and Start OSC Server Thread
    dispatcher = Dispatcher()
    dispatcher.set_default_handler(osc_handler)
    osc_server = ThreadingOSCUDPServer(
        (config["osc_server_ip"], config["osc_server_port"]), dispatcher
    )
    osc_thread = threading.Thread(target=osc_server.serve_forever, daemon=True)
    osc_thread.start()
    print(f"OSC Server listening on {osc_server.server_address}")
    
    # Start Flask App (this will be the main thread)
    print(f"Starting Flask API server on http://localhost:3001")
    app.run(host="0.0.0.0", port=3001)