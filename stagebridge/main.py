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
    """
    Restart only the API/Admin Flask server.
    Runs the restart logic in a background thread to avoid blocking HTTP handlers.
    """
    def do_restart():
        global global_api_admin_app, global_api_admin_server, global_api_server_thread
        global is_api_admin_restarting

        if is_api_admin_restarting.is_set():
            print("INFO: API/Admin restart already in progress. Ignoring redundant call.")
            sys.stdout.flush()
            return

        is_api_admin_restarting.set()
        print("INFO: [restart_api_admin_service] Initiating API/Admin server restart...")
        sys.stdout.flush()

        # Shut down the existing server and wait for the thread to exit
        if global_api_admin_server:
            print("INFO: [restart_api_admin_service] Shutting down existing API/Admin server...")
            sys.stdout.flush()
            global_api_admin_server.shutdown()
            if (
                global_api_server_thread
                and global_api_server_thread.is_alive()
                and threading.current_thread() != global_api_server_thread
            ):
                print("INFO: [restart_api_admin_service] Waiting for old server thread to stop...")
                global_api_server_thread.join(timeout=5)
        else:
            print("INFO: No existing API/Admin server found to shut down.")

        # Reload configuration and create a new Flask app instance
        print("INFO: [restart_api_admin_service] Reloading configuration...")
        sys.stdout.flush()
        load_config()

        print("INFO: [restart_api_admin_service] Re-creating API/Admin Flask app...")
        sys.stdout.flush()
        global_api_admin_app = create_app(restart_callback=restart_api_admin_service)
        global_api_admin_app.logger.setLevel(logging.INFO)

        # Start the new server on the same port
        print(f"INFO: [restart_api_admin_service] Starting new Flask API/Admin server on http://0.0.0.0:{FLASK_API_PORT}")
        sys.stdout.flush()
        try:
            global_api_admin_server = make_server("0.0.0.0", FLASK_API_PORT, global_api_admin_app)
            global_api_server_thread = threading.Thread(
                target=global_api_admin_server.serve_forever,
                daemon=True
            )
            global_api_server_thread.start()
            print("INFO: [restart_api_admin_service] New API/Admin server started successfully.")
            sys.stdout.flush()
        except Exception as e:
            print(f"ERROR: [restart_api_admin_service] Failed to start new API/Admin server: {e}")
            sys.stdout.flush()

        is_api_admin_restarting.clear()

    # Always run the restart logic in a new thread
    threading.Thread(target=do_restart, daemon=True).start()

def trigger_full_process_restart():
    """
    Cleanly exit the entire process (for systemd or supervisor to restart).
    """
    global exit_sequence_initiated
    if exit_sequence_initiated:
        print("WARNING: Full process restart sequence already initiated. Ignoring redundant call.")
        sys.stdout.flush()
        return

    print("INFO: [trigger_full_process_restart] Received full process restart command.")
    sys.stdout.flush()
    exit_sequence_initiated = True

    def do_exit():
        print("INFO: [do_exit] Thread started. Waiting 1 second before exit...")
        sys.stdout.flush()
        time.sleep(1)
        print("INFO: [do_exit] 1 second passed. Attempting sys.exit(0)...")
        sys.stdout.flush()
        os._exit(0)

    print("INFO: [trigger_full_process_restart] Starting exit thread...")
    sys.stdout.flush()
    exit_thread = threading.Thread(target=do_exit)
    exit_thread.daemon = True
    exit_thread.start()
    print("INFO: [trigger_full_process_restart] Exit thread started. Main thread continues briefly.")
    sys.stdout.flush()

# Use this as the restart callback for the API/Admin server
trigger_restart = restart_api_admin_service

def start_all_services():
    """
    Start all background services and servers.
    This function is run in a background thread so the main thread can run the GUI.
    """
    sys.stdout.flush()
    print("--- Starting StageBridge ---\n")

    # Load configuration and print MIDI devices
    load_config()
    print("--- Config loaded ---\n")

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
    global_api_admin_app = create_app(restart_callback=trigger_restart)
    client_frontend_app = create_client_app()

    # Start API/Admin server (Werkzeug) in a background thread
    print(f"Starting Flask API/Admin server on http://0.0.0.0:{FLASK_API_PORT}\n")
    global_api_admin_server = make_server("0.0.0.0", FLASK_API_PORT, global_api_admin_app)
    global_api_server_thread = threading.Thread(
        target=global_api_admin_server.serve_forever, daemon=True
    )
    global_api_server_thread.start()

    # Start client frontend server in a background thread
    print(f"Starting Flask Client Frontend server on http://0.0.0.0:{FLASK_CLIENT_PORT}\n")
    client_server_thread = threading.Thread(
        target=lambda: client_frontend_app.run(
            host="0.0.0.0", port=FLASK_CLIENT_PORT, debug=False, use_reloader=False
        ),
        daemon=True
    )
    client_server_thread.start()

    # Start discovery service for network presence
    device_name = f"StageBridge-{socket.gethostname()}"
    start_discovery_service(port=FLASK_API_PORT, device_name=device_name)

    # Configure logging for both Flask apps
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        stream=sys.stdout
    )
    global_api_admin_app.logger.setLevel(logging.INFO)
    client_frontend_app.logger.setLevel(logging.INFO)

if __name__ == "__main__":
    # Start all services in a background thread
    threading.Thread(target=start_all_services, daemon=True).start()
    # Run the Kivy GUI in the main thread
    StageBridgeApp().run()