import os
import socket
import threading
import time
import requests
import json
import concurrent.futures
from flask import Flask, render_template, send_from_directory, jsonify, request
from flask_cors import CORS
from zeroconf import Zeroconf, ServiceBrowser, ServiceInfo
import shared_state

def create_client_app():
    CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
    TEMPLATES_FOLDER = os.path.join(CURRENT_DIR, "templates")

    app = Flask(
        __name__,
        static_folder=TEMPLATES_FOLDER,
        static_url_path="/",
        template_folder=TEMPLATES_FOLDER,
    )
    
    # Apply CORS middleware
    CORS(app)

    # --- Main Client Routes ---
    @app.route("/")
    def serve_client_index():
        return render_template("client.html")

    @app.route("/fleet")
    def serve_fleet_index():
        return render_template("fleet.html")

    @app.route("/api/fleet/devices", methods=["GET"])
    def get_fleet_devices():
        """Returns a list of currently discovered StageBridge devices."""
        print(f"DEBUG: discovered_devices = {shared_state.discovered_devices}")
        
        # Filter out non-JSON-serializable fields (like the OSC client)
        devices = []
        for device_info in shared_state.discovered_devices.values():
            # Create a copy without the 'client' field
            json_safe_device = {
                'name': device_info['name'],
                'host': device_info['host'],
                'ip': device_info['ip'],
                'port': device_info['port'],
                'fqdn': device_info['fqdn']
            }
            devices.append(json_safe_device)
        
        print(f"DEBUG: Returning {len(devices)} devices")
        return jsonify(devices)

    @app.route("/api/fleet/sync", methods=["POST"])
    def sync_fleet_devices():
        """Receives RTP MIDI target IP/Port and OSC port, then updates all discovered devices."""
        data = request.get_json()
        rtp_ip = data.get("rtp_ip")
        rtp_port = data.get("rtp_port")
        osc_port = data.get("osc_port")

        if not rtp_ip or not rtp_port or not osc_port:
            return jsonify({"error": "Missing rtp_ip, rtp_port, or osc_port"}), 400

        devices_to_sync = list(shared_state.discovered_devices.values())
        
        def update_single_device(device):
            """Helper function to handle the update logic for a single device."""
            device_name = device["name"]
            device_url = f"http://{device['ip']}:{device['port']}"
            try:
                print(f"Attempting to sync {device_name} at {device_url}...")
                
                # 1. Fetch current config
                config_res = requests.get(f"{device_url}/api/config", timeout=10)
                config_res.raise_for_status()
                current_config = config_res.json()

                # 2. Update config values
                current_config["rtp_midi_target_ip"] = rtp_ip
                current_config["rtp_midi_target_port"] = rtp_port
                current_config["osc_server_port"] = osc_port

                # 3. Save updated config
                put_res = requests.put(
                    f"{device_url}/api/config",
                    json=current_config,
                    headers={"Content-Type": "application/json"},
                    timeout=10
                )
                put_res.raise_for_status()

                # 4. Restart device
                restart_res = requests.post(f"{device_url}/api/system/restart", timeout=10)
                restart_res.raise_for_status()

                print(f"Successfully synced {device_name}")
                return {"name": device_name, "status": "success"}
                
            except requests.exceptions.RequestException as e:
                error_message = f"Failed to sync {device_name}: Network or HTTP error - {e}"
                print(error_message)
                return {"name": device_name, "status": "failure", "reason": str(e)}
            except json.JSONDecodeError as e:
                error_message = f"Failed to parse JSON response for {device_name}: {e}"
                print(error_message)
                return {"name": device_name, "status": "failure", "reason": str(e)}
            except Exception as e:
                error_message = f"An unexpected error occurred for {device_name}: {e}"
                print(error_message)
                return {"name": device_name, "status": "failure", "reason": str(e)}

        # Use ThreadPoolExecutor for concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            results = list(executor.map(update_single_device, devices_to_sync))

        return jsonify(results)

    # --- Error Handlers ---
    @app.errorhandler(404)
    def not_found(e):
        # Check if it's a fleet route
        if request.path.startswith('/fleet'):
            return render_template('fleet.html'), 200
        # Otherwise serve the main client app
        return render_template("client.html"), 200

    return app