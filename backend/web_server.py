# web_server.py
import os
import json
import uuid
from flask import Flask, jsonify, request, send_file, render_template_string, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename
from mido import get_input_names, get_output_names

# Import from our other modules
import shared_state
import config_manager
from song_parser import parse_song_csv

# Define the static folder path relative to this file
STATIC_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
app = Flask(__name__, static_folder=STATIC_FOLDER)
CORS(app)

ADMIN_PAGE_TEMPLATE = """
<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>StageBridge Network Admin</title><style>body{font-family:sans-serif;background-color:#1a1a1a;color:#e0e0e0;margin:40px}.container{max-width:600px;margin:auto;background-color:#2b2b2b;padding:20px;border-radius:8px}h1,h2{border-bottom:1px solid #444;padding-bottom:10px}.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:15px;margin-bottom:20px}label{font-weight:bold}input{width:100%;padding:8px;background-color:#333;color:#e0e0e0;border:1px solid #444;border-radius:4px;box-sizing:border-box}input[readonly]{background-color:#444;cursor:not-allowed}button{background-color:#dc3545;color:white;border:none;padding:12px 20px;border-radius:5px;cursor:pointer;font-size:1em}.warning{color:#ffc107;margin-top:20px}</style></head><body><div class="container"><h1>Network Admin</h1><p>Configure core network settings. Changes require a service restart.</p><form method="POST"><h2>OSC Server (Incoming)</h2><div class="form-grid"><div><label for="osc_server_ip">Listen IP Address</label><input type="text" id="osc_server_ip" name="osc_server_ip" value="{{ config.osc_server_ip }}" readonly></div><div><label for="osc_server_port">Listen Port</label><input type="number" id="osc_server_port" name="osc_server_port" value="{{ config.osc_server_port }}" required></div></div><h2>RTP-MIDI (Outgoing)</h2><div class="form-grid"><div><label for="rtp_midi_target_ip">Target IP Address</label><input type="text" id="rtp_midi_target_ip" name="rtp_midi_target_ip" value="{{ config.rtp_midi_target_ip }}" required></div><div><label for="rtp_midi_target_port">Target Port</label><input type="number" id="rtp_midi_target_port" name="rtp_midi_target_port" value="{{ config.rtp_midi_target_port }}" required></div></div><button type="submit">Save & Restart Service</button><p class="warning"><strong>Warning:</strong> Saving will immediately restart the entire StageBridge service.</p></form></div></body></html>
"""

def create_app(restart_callback):
    """Creates and configures the Flask application."""
    
    @app.route("/")
    def serve_index(): return send_from_directory(app.static_folder, 'index.html')

    @app.route("/admin", methods=["GET", "POST"])
    def admin_page():
        if request.method == "POST":
            shared_state.config["osc_server_port"] = int(request.form["osc_server_port"])
            shared_state.config["rtp_midi_target_ip"] = request.form["rtp_midi_target_ip"]
            shared_state.config["rtp_midi_target_port"] = int(request.form["rtp_midi_target_port"])
            config_manager.save_config()
            restart_callback()
            return "<h1>Configuration saved. Restarting service...</h1>"
        return render_template_string(ADMIN_PAGE_TEMPLATE, config=shared_state.config)

    @app.route("/api/system/restart", methods=["POST"])
    def system_restart():
        restart_callback()
        return jsonify({"message": "Server is restarting..."})

    @app.route("/api/status", methods=["GET"])
    def get_status():
        return jsonify({
            "service": "OSC-MIDI StageBridge", "status": "running",
            "midi_input": shared_state.midi_in_port.name if shared_state.midi_in_port else "Not Connected",
            "midi_output": shared_state.midi_out_port.name if shared_state.midi_out_port else "Not Connected"
        })

    @app.route("/api/midi-ports", methods=["GET"])
    def get_midi_ports_api(): return jsonify({"inputs": get_input_names(), "outputs": get_output_names()})

    @app.route("/api/config", methods=["GET", "PUT"])
    def manage_config():
        if request.method == "GET": return jsonify(shared_state.config)
        elif request.method == "PUT":
            shared_state.config.update(request.json)
            config_manager.save_config()
            return jsonify({"message": "Config updated."})

    @app.route("/api/config/download", methods=["GET"])
    def download_config(): return send_file(config_manager.CONFIG_FILE, as_attachment=True, download_name="config.json")

    @app.route("/api/config/upload", methods=["POST"])
    def upload_config():
        if "file" not in request.files: return jsonify({"error": "No file part"}), 400
        file = request.files["file"]
        if file.filename == "": return jsonify({"error": "No file selected"}), 400
        if file and file.filename.endswith(".json"):
            try:
                new_config_data = json.load(file)
                file.seek(0)
                with open(config_manager.CONFIG_FILE, "w") as f: json.dump(new_config_data, f, indent=2)
                config_manager.load_config()
                return jsonify({"message": "Configuration uploaded successfully."})
            except Exception as e: return jsonify({"error": f"An error occurred: {e}"}), 500
        return jsonify({"error": "Invalid file type"}), 400

    @app.route("/api/songs/upload", methods=["POST"])
    def upload_song_csv():
        if "file" not in request.files: return jsonify({"error": "No file part"}), 400
        file, song_title, setlist_number_str = request.files["file"], request.form.get("song_title"), request.form.get("setlist_number")
        if not all([file, song_title, setlist_number_str]): return jsonify({"error": "Missing form data"}), 400
        try:
            setlist_number = int(setlist_number_str) - 1
            parser_settings = shared_state.config.get("song_parser_settings", {})
            new_mappings = parse_song_csv(file.stream, song_title, setlist_number, parser_settings)
            if not new_mappings: return jsonify({"message": "No new mappings generated."}), 200
            shared_state.config["osc_mappings"].extend(new_mappings)
            config_manager.save_config()
            return jsonify({"message": f"Successfully added {len(new_mappings)} mappings for '{song_title}'."})
        except Exception as e: return jsonify({"error": f"An error occurred during parsing: {e}"}), 500

    @app.route("/api/mappings", methods=["POST"])
    def add_mapping():
        mapping = request.json
        mapping["id"] = uuid.uuid4().hex
        shared_state.config["osc_mappings"].append(mapping)
        config_manager.save_config()
        return jsonify(mapping), 201

    @app.route("/api/mappings/<mapping_id>", methods=["PUT", "DELETE"])
    def manage_mapping(mapping_id):
        mappings = shared_state.config["osc_mappings"]
        mapping_found = next((m for m in mappings if m["id"] == mapping_id), None)
        if not mapping_found: return jsonify({"error": "Mapping not found"}), 404
        if request.method == "PUT":
            mapping_found.update(request.json)
            config_manager.save_config()
            return jsonify(mapping_found)
        elif request.method == "DELETE":
            shared_state.config["osc_mappings"] = [m for m in mappings if m["id"] != mapping_id]
            config_manager.save_config()
            return jsonify({"message": "Mapping deleted"}), 200
            
    return app