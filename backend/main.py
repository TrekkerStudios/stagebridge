FLASK_API_PORT = 3001


import sys
import os
import time
import threading
import socket
from mido import get_input_names, get_output_names

# Import from our new modules
from config_manager import load_config
from midi_handler import initialize_ports, start_midi_passthrough
from osc_server import start_osc_server
from web_server import create_app
from discovery import start_discovery_service

def trigger_restart():
    """Exits the script cleanly, relying on systemd to restart it."""
    print("INFO: Received restart command. Exiting for systemd to handle restart.")
    def do_exit():
        time.sleep(1)
        sys.exit(0)
    
    exit_thread = threading.Thread(target=do_exit)
    exit_thread.daemon = True
    exit_thread.start()

if __name__ == "__main__":
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
    
    # 6. Run the web server (this will block and be the main thread)
    print(f"Starting Flask API server on http://0.0.0.0:{FLASK_API_PORT}")
    app.run(host="0.0.0.0", port=FLASK_API_PORT)