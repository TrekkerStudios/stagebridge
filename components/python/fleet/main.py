PORT = 3002

import socket
import threading
import time
import requests
import json
import signal
import sys
import os

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS # For CORS middleware

from zeroconf import Zeroconf, ServiceBrowser, ServiceStateChange, ServiceInfo

# --- Zeroconf Discovery Setup ---
# Use a dictionary to store discovered devices, keyed by their FQDN for easy updates/deletions.
discovered_devices = {}
zeroconf_instance = None
zeroconf_browser = None
ZEROCONF_SERVICE_TYPE = "_stagebridge-api._tcp.local."

class StageBridgeListener:
    """
    A listener for Zeroconf service discovery events.
    Handles adding and removing discovered StageBridge devices.
    """
    def add_service(self, zeroconf: Zeroconf, type: str, name: str) -> None:
        """Called when a service is discovered."""
        info = zeroconf.get_service_info(type, name, timeout=3000) # Give it some time to get full info
        if info:
            ip_address = None
            if info.addresses:
                # Addresses are bytes (e.g., b'\xc0\xa8\x01\n'). Decode them.
                for addr_bytes in info.addresses:
                    try:
                        # Assuming IPv4 based on original JS example (addresses?.[0])
                        ip_address = str(socket.inet_ntoa(addr_bytes))
                        break # Take the first valid IPv4 address
                    except OSError:
                        # If it's an IPv6 address or other issue, continue to the next
                        continue

            # `info.server` typically holds the Fully Qualified Domain Name (FQDN)
            # which is a good unique key for the discovered_devices dictionary.
            if ip_address and info.port:
                print(f"Device discovered: {info.name} at {ip_address}:{info.port}")
                discovered_devices[info.server] = {
                    "name": info.name,
                    "host": info.server, # The FQDN of the service
                    "ip": ip_address,
                    "port": info.port,
                    "fqdn": info.server, # Using server as FQDN for consistency with JS
                }
            else:
                print(f"Device discovered but no valid IP/Port found: {info.name}")
        else:
            print(f"Could not get service info for: {name} ({type})")


    def remove_service(self, zeroconf: Zeroconf, type: str, name: str) -> None:
        """Called when a service goes offline."""
        # Attempt to get info to determine the FQDN to remove,
        # but service might be completely gone.
        info = zeroconf.get_service_info(type, name)
        fqdn_to_remove = info.server if info else f"{name}.{type}" # Fallback
        
        if fqdn_to_remove in discovered_devices:
            print(f"Device went away: {discovered_devices[fqdn_to_remove]['name']}")
            del discovered_devices[fqdn_to_remove]
        else:
            print(f"Device went away (not found in current list): {name}")

def start_zeroconf_discovery():
    """Initializes and starts the Zeroconf discovery browser."""
    global zeroconf_instance, zeroconf_browser
    zeroconf_instance = Zeroconf()
    listener = StageBridgeListener()
    print(f"Starting network discovery for StageBridge devices ({ZEROCONF_SERVICE_TYPE})...")
    # ServiceBrowser runs in its own thread by default with Zeroconf 0.50.0+
    zeroconf_browser = ServiceBrowser(zeroconf_instance, ZEROCONF_SERVICE_TYPE, listener)

def stop_zeroconf_discovery():
    """Shuts down the Zeroconf instance."""
    global zeroconf_instance, zeroconf_browser
    if zeroconf_browser:
        # As of python-zeroconf 0.50.0, ServiceBrowser manages its own thread,
        # closing the Zeroconf instance handles stopping the browser cleanly.
        zeroconf_browser = None 
    if zeroconf_instance:
        print("Shutting down discovery...")
        zeroconf_instance.close()
        zeroconf_instance = None

# --- Flask Web Server Setup ---
# Set static_folder to 'public' and static_url_path to '/'
# This tells Flask to serve files from the 'public' directory when requests
# come in for the root URL or direct file paths (e.g., /style.css).
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PUBLIC_FOLDER = os.path.join(CURRENT_DIR, "public")
app = Flask(__name__, static_folder=PUBLIC_FOLDER, static_url_path='/')

# Apply CORS middleware to allow cross-origin requests, similar to Hono's `cors()`.
CORS(app)

@app.route("/")
def serve_index():
    """Serves the index.html file when accessing the root URL."""
    # send_from_directory is the recommended way to serve files from a directory
    # The first argument is the directory (inferred from static_folder if not explicit)
    # The second argument is the filename to serve
    return send_from_directory(app.static_folder, 'index.html')

# --- API Routes ---

@app.route("/api/devices", methods=["GET"])
def get_devices():
    """Returns a list of currently discovered StageBridge devices."""
    # Convert dictionary values to a list of device objects
    devices = list(discovered_devices.values())
    return jsonify(devices)

import concurrent.futures

@app.route("/api/sync", methods=["POST"])
def sync_devices():
    """
    Receives RTP MIDI target IP and Port, then updates all discovered devices.
    Each device's config is fetched, updated, saved, and then the device is restarted.
    """
    data = request.get_json()
    rtp_ip = data.get("rtp_ip")
    rtp_port = data.get("rtp_port")

    if not rtp_ip or not rtp_port:
        return jsonify({"error": "Missing rtp_ip or rtp_port"}), 400

    devices_to_sync = list(discovered_devices.values())
    
    def update_single_device(device):
        """
        Helper function to handle the update logic for a single device.
        Designed to be run concurrently in a thread pool.
        """
        device_name = device["name"]
        device_url = f"http://{device['ip']}:{device['port']}"
        try:
            print(f"Attempting to sync {device_name} at {device_url}...")
            # 1. Fetch current config
            config_res = requests.get(f"{device_url}/api/config", timeout=10)
            config_res.raise_for_status() # Raise HTTPError for 4xx/5xx responses
            current_config = config_res.json()

            # 2. Update config values
            current_config["rtp_midi_target_ip"] = rtp_ip
            current_config["rtp_midi_target_port"] = rtp_port

            # 3. Save updated config
            put_res = requests.put(
                f"{device_url}/api/config",
                json=current_config, # requests handles converting dict to JSON body
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
            # Catch common network/HTTP errors (ConnectionError, Timeout, HTTPError, etc.)
            error_message = f"Failed to sync {device_name}: Network or HTTP error - {e}"
            print(error_message)
            return {"name": device_name, "status": "failure", "reason": str(e)}
        except json.JSONDecodeError as e:
            error_message = f"Failed to parse JSON response for {device_name}: {e}"
            print(error_message)
            return {"name": device_name, "status": "failure", "reason": str(e)}
        except Exception as e:
            # Catch any other unexpected errors
            error_message = f"An unexpected error occurred for {device_name}: {e}"
            print(error_message)
            return {"name": device_name, "status": "failure", "reason": str(e)}

    # Use ThreadPoolExecutor for concurrent requests, similar to Promise.allSettled
    # max_workers can be adjusted based on expected number of devices
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        # map submits tasks and returns an iterator of results in the order tasks were submitted
        results = list(executor.map(update_single_device, devices_to_sync))

    return jsonify(results)

# --- Static File Serving ---
# Flask's `static_folder` and `static_url_path` configuration
# already handles serving `index.html` for '/' and other files like
# `/style.css` or `/client.js` from the 'public' directory.
# No explicit routes are needed for these.

# --- Graceful Shutdown Handler ---
def shutdown_handler(signum, frame):
    """
    Handles SIGINT (Ctrl+C) to gracefully shut down the application,
    including stopping Zeroconf discovery.
    """
    print("\nReceived SIGINT. Initiating graceful shutdown...")
    stop_zeroconf_discovery()
    # If running with app.run() in development, sys.exit() will stop it.
    # In production (e.g., with Gunicorn), the WSGI server manages its own shutdown.
    sys.exit(0)

# Register the shutdown handler for SIGINT
signal.signal(signal.SIGINT, shutdown_handler)

# --- Start the Server ---
if __name__ == "__main__":
    
    # Start Zeroconf discovery as soon as the app begins
    # It runs in background threads managed by python-zeroconf.
    start_zeroconf_discovery() 
    
    print(f"Fleet Manager server running at http://localhost:{PORT}")
    try:
        # Run the Flask development server.
        # Set `debug=False` for better signal handling in a production-like scenario.
        app.run(host="0.0.0.0", port=PORT, debug=False)
    finally:
        # Ensure Zeroconf is closed even if the Flask app exits unexpectedly
        stop_zeroconf_discovery()