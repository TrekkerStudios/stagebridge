FLASK_API_PORT = 3001
FLASK_CLIENT_PORT = 3000

import sys
import os
import time
import threading
import socket
import logging
from mido import get_input_names, get_output_names
from werkzeug.serving import make_server

from config_manager import load_config
from midi_handler import initialize_ports, start_midi_passthrough
from osc_server import start_osc_server
from web_server import create_app
from client_web_server import create_client_app
from discovery import start_discovery_service

# Import the Kivy GUI app
from gui import StageBridgeApp

# Global state for API/Admin server management
exit_sequence_initiated = False
global_api_admin_app = None
global_api_admin_server = None
global_api_server_thread = None
is_api_admin_restarting = threading.Event()

def restart_api_admin_service():
    """Restart only the API/Admin Flask server."""
    def do_restart():
        global global_api_admin_app, global_api_admin_server, global_api_server_thread
        global is_api_admin_restarting

        if is_api_admin_restarting.is_set():
            print("INFO: API/Admin restart already in progress. Ignoring redundant call.")
            return

        is_api_admin_restarting.set()
        print("INFO: Initiating API/Admin server restart...")

        # Shut down existing server
        if global_api_admin_server:
            print("INFO: Shutting down existing API/Admin server...")
            global_api_admin_server.shutdown()
            if (global_api_server_thread and global_api_server_thread.is_alive() 
                and threading.current_thread() != global_api_server_thread):
                global_api_server_thread.join(timeout=5)

        # Reload configuration
        print("INFO: Reloading configuration...")
        load_config()

        # Create new Flask app
        print("INFO: Re-creating API/Admin Flask app...")
        global_api_admin_app = create_app(restart_callback=restart_api_admin_service)

        # Start new server
        print(f"INFO: Starting new Flask API/Admin server on port {FLASK_API_PORT}")
        try:
            global_api_admin_server = make_server("0.0.0.0", FLASK_API_PORT, global_api_admin_app)
            global_api_server_thread = threading.Thread(
                target=global_api_admin_server.serve_forever, daemon=True
            )
            global_api_server_thread.start()
            print("INFO: New API/Admin server started successfully.")
        except Exception as e:
            print(f"ERROR: Failed to start new API/Admin server: {e}")

        is_api_admin_restarting.clear()

    threading.Thread(target=do_restart, daemon=True).start()

def start_all_services():
    """Start all background services and servers."""
    print("--- Starting StageBridge ---\n")

    # Load configuration
    load_config()
    print("--- Config loaded ---\n")

    # Print MIDI devices
    print("\n--- Detected MIDI Devices ---")
    try:
        print(f"Available MIDI Inputs: {get_input_names()}")
        print(f"Available MIDI Outputs: {get_output_names()}")
    except Exception as e:
        print(f"Error detecting MIDI devices: {e}")
    print("---------------------------\n")

    # Initialize MIDI and start background services
    initialize_ports()
    print("--- Ports initialized ---\n")

    start_midi_passthrough()
    start_osc_server()
    print("--- MIDI and OSC services started ---\n")

    # Create Flask apps
    global global_api_admin_app, global_api_admin_server, global_api_server_thread
    global_api_admin_app = create_app(restart_callback=restart_api_admin_service)
    client_frontend_app = create_client_app()

    # Start API/Admin server
    print(f"Starting Flask API/Admin server on http://0.0.0.0:{FLASK_API_PORT}\n")
    global_api_admin_server = make_server("0.0.0.0", FLASK_API_PORT, global_api_admin_app)
    global_api_server_thread = threading.Thread(
        target=global_api_admin_server.serve_forever, daemon=True
    )
    global_api_server_thread.start()

    # Start client frontend server
    print(f"Starting Flask Client Frontend server on http://0.0.0.0:{FLASK_CLIENT_PORT}\n")
    client_server_thread = threading.Thread(
        target=lambda: client_frontend_app.run(
            host="0.0.0.0", port=FLASK_CLIENT_PORT, debug=False, use_reloader=False
        ),
        daemon=True
    )
    client_server_thread.start()

    # **FIX: Start discovery service AFTER servers are running**
    print("--- Starting discovery service ---")
    device_name = f"StageBridge-{socket.gethostname()}"
    start_discovery_service(port=FLASK_API_PORT, device_name=device_name)
    print(f"--- Discovery service started for {device_name} ---\n")

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        stream=sys.stdout
    )

if __name__ == "__main__":
    # Start all services in a background thread
    threading.Thread(target=start_all_services, daemon=True).start()
    # Run the Kivy GUI in the main thread
    StageBridgeApp().run()