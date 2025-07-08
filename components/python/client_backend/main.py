FLASK_API_PORT = 3001


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
from web_server import create_app
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
    
    # 5. Create the Flask app, passing the restart function as a callback
    app = create_app(restart_callback=trigger_restart)
    
    device_name = f"StageBridge-{socket.gethostname()}"
    start_discovery_service(port=FLASK_API_PORT, device_name=device_name)
    
    logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    stream=sys.stdout) # You can try sys.stderr too
    app.logger.setLevel(logging.INFO)
    
    # 6. Run the web server (this will block and be the main thread)
    print(f"Starting Flask API server on http://0.0.0.0:{FLASK_API_PORT}")
    app.run(host="0.0.0.0", port=FLASK_API_PORT)