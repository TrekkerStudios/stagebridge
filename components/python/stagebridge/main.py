FLASK_API_PORT = 3001
FLASK_CLIENT_PORT = 3000 # NEW: Define port for client frontend


import sys
import os
import time
import threading
import socket
import logging
from mido import get_input_names, get_output_names

# Import from our new modules
from config_manager import load_config
from midi_handler import initialize_ports, start_midi_passthrough
from osc_server import start_osc_server
from web_server import create_app  # Existing API/Admin server
from client_web_server import create_client_app  # NEW: Import the client server
from discovery import start_discovery_service

# Add a global flag to check if exit sequence started
exit_sequence_initiated = False

def trigger_restart():
    """Exits the script cleanly, relying on systemd to restart it."""
    global exit_sequence_initiated
    if exit_sequence_initiated:
        print("WARNING: Restart sequence already initiated. Ignoring redundant call.")
        sys.stdout.flush()
        return

    print("INFO: [trigger_restart] Received restart command.")
    sys.stdout.flush() # Ensure this initial print is flushed

    exit_sequence_initiated = True

    def do_exit():
        print("INFO: [do_exit] Thread started. Waiting 1 second before exit...")
        sys.stdout.flush()
        time.sleep(1) # Gives the HTTP response a chance to go out
        print("INFO: [do_exit] 1 second passed. Attempting sys.exit(0)...")
        sys.stdout.flush()
        os._exit(0) # Exits the current Python process
    
    print("INFO: [trigger_restart] Starting exit thread...")
    sys.stdout.flush()
    exit_thread = threading.Thread(target=do_exit)
    exit_thread.daemon = True # Allows program to exit if only this thread remains
    exit_thread.start()
    print("INFO: [trigger_restart] Exit thread started. Main thread continues briefly.")
    sys.stdout.flush()

if __name__ == "__main__":
    sys.stdout.flush() # Flush initial print
    print("--- Starting StageBridge Service ---")
    
    # 1. Load configuration into shared state
    load_config()
    
    # 2. Print detected MIDI devices for debugging
    print("\n--- Detected MIDI Devices ---")
    try:
        print(f"Available MIDI Inputs: {get_input_names()}")
        print(f"Available MIDI Outputs: {get_output_names()}")
    except Exception as e:
        print(f"Error detecting MIDI devices: {e}")
    print("---------------------------\n")
    
    # 3. Initialize all MIDI ports based on the loaded config
    initialize_ports()
    
    # 4. Start background services (threads)
    start_midi_passthrough()
    start_osc_server()
    
    # 5. Create both Flask apps
    # Main API/Admin Web Server (port 3001)
    api_admin_app = create_app(restart_callback=trigger_restart)
    
    # Client Frontend Web Server (port 3000)
    client_frontend_app = create_client_app()

    # 6. Start the API/Admin Flask server in a separate thread
    print(f"Starting Flask API/Admin server on http://0.0.0.0:{FLASK_API_PORT}")
    api_server_thread = threading.Thread(
        target=lambda: api_admin_app.run(
            host="0.0.0.0", port=FLASK_API_PORT, debug=False, use_reloader=False
        )
    )
    api_server_thread.daemon = True # Allow main program to exit if this thread is only one left
    api_server_thread.start()

    # 7. Start the Client Frontend Flask server in a separate thread
    print(f"Starting Flask Client Frontend server on http://0.0.0.0:{FLASK_CLIENT_PORT}")
    client_server_thread = threading.Thread(
        target=lambda: client_frontend_app.run(
            host="0.0.0.0", port=FLASK_CLIENT_PORT, debug=False, use_reloader=False
        )
    )
    client_server_thread.daemon = True # Allow main program to exit if this thread is only one left
    client_server_thread.start()

    # 8. Start Discovery Service
    # Discovery should point to the API port, as it exposes the core service.
    device_name = f"StageBridge-{socket.gethostname()}"
    start_discovery_service(port=FLASK_API_PORT, device_name=device_name) 

    # 9. Configure logging (can be applied to both apps implicitly)
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(message)s',
                        stream=sys.stdout)
    api_admin_app.logger.setLevel(logging.INFO)
    client_frontend_app.logger.setLevel(logging.INFO)

    # Keep the main thread alive indefinitely to allow Flask servers to run
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nINFO: Ctrl+C detected. Shutting down...")
        sys.exit(0)