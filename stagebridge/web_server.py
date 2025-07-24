import os
import json
import uuid
import socket
from flask import (
    Flask,
    jsonify,
    request,
    send_file,
    render_template,
    send_from_directory,
)
from flask_cors import CORS
from werkzeug.utils import secure_filename
from mido import get_input_names, get_output_names

import shared_state
import config_manager
from song_parser import parse_song_csv

TEMPLATE_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")

def create_app(restart_callback):
    app = Flask(__name__, static_folder=TEMPLATE_FOLDER, template_folder=TEMPLATE_FOLDER)
    CORS(app)

    @app.route("/")
    def serve_index():
        return "<h1>StageBridge Admin Server</h1><p><a href='/admin'>Go to Admin Panel</a></p>"

    @app.route("/style.css")
    def serve_css():
        return send_from_directory(app.static_folder, "style.css")

    @app.route("/client.js")
    def serve_client_js():
        return send_from_directory(app.static_folder, "client.js")

    @app.route("/fleet.js")
    def serve_fleet_js():
        return send_from_directory(app.static_folder, "fleet.js")

    @app.route("/admin", methods=["GET", "POST"])
    def admin_page():
        if request.method == "POST":
            shared_state.config["osc_server_port"] = int(
                request.form["osc_server_port"]
            )
            shared_state.config["rtp_midi_target_ip"] = request.form[
                "rtp_midi_target_ip"
            ]
            shared_state.config["rtp_midi_target_port"] = int(
                request.form["rtp_midi_target_port"]
            )
            config_manager.save_config()
            restart_callback()
            return "<h1>Configuration saved. Restarting service...</h1>"
        return render_template("admin.html", config=shared_state.config)

    @app.route("/api/system/restart", methods=["POST"])
    def system_restart():
        restart_callback()
        return jsonify({"message": "Server is restarting..."})

    @app.route("/api/status", methods=["GET"])
    def get_status():
        return jsonify(
            {
                "service": "OSC-MIDI StageBridge",
                "status": "running",
                "midi_input": (
                    shared_state.midi_in_port.name
                    if shared_state.midi_in_port
                    else "Not Connected"
                ),
                "midi_output": (
                    shared_state.midi_out_port.name
                    if shared_state.midi_out_port
                    else "Not Connected"
                ),
            }
        )

    @app.route("/api/midi-ports", methods=["GET"])
    def get_midi_ports_api():
        return jsonify({"inputs": get_input_names(), "outputs": get_output_names()})

    @app.route("/api/config", methods=["GET", "PUT"])
    def manage_config():
        if request.method == "GET":
            return jsonify(shared_state.config)
        elif request.method == "PUT":
            shared_state.config.update(request.json)
            config_manager.save_config()
            return jsonify({"message": "Config updated."})
        
    @app.route("/api/system/ip", methods=["GET"])
    def get_system_ip():
        try:
            # Try multiple methods to get the actual IP address
            local_ip = None
            
            # Method 1: Try socket connection method first (most reliable)
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.settimeout(0)
                # Connect to a reserved IP that won't actually send data
                s.connect(('8.8.8.8', 80))
                local_ip = s.getsockname()[0]
                s.close()
                if not local_ip.startswith('127.'):
                    return jsonify({"ip_address": local_ip})
            except:
                pass
            
            # Method 2: Try hostname resolution
            try:
                hostname = socket.gethostname()
                local_ip = socket.gethostbyname(hostname)
                if not local_ip.startswith('127.'):
                    return jsonify({"ip_address": local_ip})
            except:
                pass
            
            # Method 3: Try getting IP from network interfaces (requires netifaces if available)
            try:
                import netifaces
                for interface in netifaces.interfaces():
                    addrs = netifaces.ifaddresses(interface)
                    if netifaces.AF_INET in addrs:
                        for addr in addrs[netifaces.AF_INET]:
                            ip = addr['addr']
                            if not ip.startswith('127.') and not ip.startswith('169.254.'):
                                return jsonify({"ip_address": ip})
            except ImportError:
                pass
            except:
                pass
            
            # Method 4: Try to get IP from OSC server configuration
            try:
                # The OSC server might be bound to a specific IP
                osc_server_ip = shared_state.config.get('osc_server_ip', '0.0.0.0')
                if osc_server_ip != '0.0.0.0' and not osc_server_ip.startswith('127.'):
                    return jsonify({"ip_address": osc_server_ip})
            except:
                pass
            
            # Method 5: Try alternative socket method with different target
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.settimeout(0)
                # Try connecting to local network gateway
                s.connect(('192.168.1.1', 80))
                local_ip = s.getsockname()[0]
                s.close()
                if not local_ip.startswith('127.'):
                    return jsonify({"ip_address": local_ip})
            except:
                pass
            
            # Fallback: return 127.0.0.1
            return jsonify({"ip_address": "127.0.0.1"})
        
        except Exception as e:
            return jsonify({
                "error": f"Could not determine IP address: {str(e)}",
                "ip_address": "127.0.0.1"
            }), 500

    @app.route("/api/config/download", methods=["GET"])
    def download_config():
        return send_file(
            config_manager.CONFIG_FILE, as_attachment=True, download_name="config.json"
        )

    @app.route("/api/config/upload", methods=["POST"])
    def upload_config():
        if "file" not in request.files:
            return jsonify({"error": "No file part"}), 400
        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "No file selected"}), 400
        if file and file.filename.endswith(".json"):
            try:
                new_config_data = json.load(file)
                file.seek(0)
                with open(config_manager.CONFIG_FILE, "w") as f:
                    json.dump(new_config_data, f, indent=2)
                config_manager.load_config()
                return jsonify({"message": "Configuration uploaded successfully."})
            except Exception as e:
                return jsonify({"error": f"An error occurred: {e}"}), 500
        return jsonify({"error": "Invalid file type"}), 400

    @app.route("/api/songs/upload", methods=["POST"])
    def upload_song_csv():
        if "file" not in request.files:
            return jsonify({"error": "No file part"}), 400
        file, song_title, setlist_number_str = (
            request.files["file"],
            request.form.get("song_title"),
            request.form.get("setlist_number"),
        )
        if not all([file, song_title, setlist_number_str]):
            return jsonify({"error": "Missing form data"}), 400
        try:
            setlist_number = int(setlist_number_str) - 1
            parser_settings = shared_state.config.get("song_parser_settings", {})
            new_mappings = parse_song_csv(
                file.stream, song_title, setlist_number, parser_settings
            )
            if not new_mappings:
                return jsonify({"message": "No new mappings generated."}), 200
            shared_state.config["osc_mappings"].extend(new_mappings)
            config_manager.save_config()
            return jsonify(
                {
                    "message": f"Successfully added {len(new_mappings)} mappings for '{song_title}'."
                }
            )
        except Exception as e:
            return jsonify({"error": f"An error occurred during parsing: {e}"}), 500

    @app.route("/api/mappings", methods=["POST", "DELETE"])
    def manage_mappings_plural():
        if request.method == "POST":
            mapping = request.json
            mapping["id"] = uuid.uuid4().hex
            shared_state.config["osc_mappings"].append(mapping)
            config_manager.save_config()
            return jsonify(mapping), 201
        elif request.method == "DELETE":
            data = request.get_json()
            if not data or "ids" not in data or not isinstance(data["ids"], list):
                return (
                    jsonify(
                        {"error": "Invalid request body. 'ids' array is required."}
                    ),
                    400,
                )
            ids_to_delete = set(data["ids"])
            current_mappings = shared_state.config["osc_mappings"]
            updated_mappings = [
                m for m in current_mappings if m.get("id") not in ids_to_delete
            ]
            shared_state.config["osc_mappings"] = updated_mappings
            config_manager.save_config()
            return jsonify(
                {"message": f"{len(ids_to_delete)} mappings deleted successfully."}
            )

    @app.route("/api/mappings/<mapping_id>", methods=["PUT", "DELETE"])
    def manage_mapping(mapping_id):
        mappings = shared_state.config["osc_mappings"]
        mapping_found = next((m for m in mappings if m["id"] == mapping_id), None)
        if not mapping_found:
            return jsonify({"error": "Mapping not found"}), 404
        if request.method == "PUT":
            mapping_found.update(request.json)
            config_manager.save_config()
            return jsonify(mapping_found)
        elif request.method == "DELETE":
            shared_state.config["osc_mappings"] = [
                m for m in mappings if m["id"] != mapping_id
            ]
            config_manager.save_config()
            return jsonify({"message": "Mapping deleted"}), 200

    @app.route("/api/mappings/upload-json", methods=["POST"])
    def upload_json_mappings():
        if not request.is_json:
            return jsonify({"error": "Request must be JSON"}), 400
        try:
            new_mappings_data = request.json
            if not isinstance(new_mappings_data, list):
                return jsonify({"error": "Expected a JSON array of mappings"}), 400
            current_mappings_dict = {
                m["osc_address"]: m for m in shared_state.config.get("osc_mappings", [])
            }
            added_count = 0
            updated_count = 0
            for new_mapping in new_mappings_data:
                if "osc_address" not in new_mapping:
                    print(
                        f"Warning: Skipping mapping due to missing 'osc_address': {new_mapping}"
                    )
                    continue
                osc_address = new_mapping["osc_address"]
                if "id" not in new_mapping or not isinstance(new_mapping["id"], str):
                    new_mapping["id"] = uuid.uuid4().hex
                if osc_address in current_mappings_dict:
                    current_mappings_dict[osc_address] = new_mapping
                    updated_count += 1
                else:
                    current_mappings_dict[osc_address] = new_mapping
                    added_count += 1
            shared_state.config["osc_mappings"] = list(current_mappings_dict.values())
            config_manager.save_config()
            return jsonify(
                {
                    "message": f"Mappings uploaded successfully. Added: {added_count}, Updated: {updated_count}.",
                    "added_count": added_count,
                    "updated_count": updated_count,
                }
            )
        except json.JSONDecodeError:
            return jsonify({"error": "Invalid JSON format"}), 400
        except Exception as e:
            return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

    return app