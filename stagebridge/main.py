import sys
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
from gui import StageBridgeApp

FLASK_API_PORT = 3001
FLASK_CLIENT_PORT = 3000

global_api_admin_app = None
global_api_admin_server = None
global_api_server_thread = None
is_api_admin_restarting = threading.Event()

def restart_api_admin_service():
    def do_restart():
        global global_api_admin_app, global_api_admin_server, global_api_server_thread, is_api_admin_restarting

        if is_api_admin_restarting.is_set():
            return

        is_api_admin_restarting.set()
        
        if global_api_admin_server:
            global_api_admin_server.shutdown()
            if (global_api_server_thread and global_api_server_thread.is_alive() 
                and threading.current_thread() != global_api_server_thread):
                global_api_server_thread.join(timeout=5)

        load_config()
        global_api_admin_app = create_app(restart_callback=restart_api_admin_service)

        try:
            global_api_admin_server = make_server("0.0.0.0", FLASK_API_PORT, global_api_admin_app)
            global_api_server_thread = threading.Thread(
                target=global_api_admin_server.serve_forever, daemon=True
            )
            global_api_server_thread.start()
        except Exception as e:
            print(f"Failed to restart API server: {e}")

        is_api_admin_restarting.clear()

    threading.Thread(target=do_restart, daemon=True).start()

def start_all_services():
    load_config()
    
    try:
        print(f"MIDI Inputs: {get_input_names()}")
        print(f"MIDI Outputs: {get_output_names()}")
    except Exception as e:
        print(f"MIDI device error: {e}")

    initialize_ports()
    start_midi_passthrough()
    start_osc_server()

    global global_api_admin_app, global_api_admin_server, global_api_server_thread
    global_api_admin_app = create_app(restart_callback=restart_api_admin_service)
    client_frontend_app = create_client_app()

    global_api_admin_server = make_server("0.0.0.0", FLASK_API_PORT, global_api_admin_app)
    global_api_server_thread = threading.Thread(
        target=global_api_admin_server.serve_forever, daemon=True
    )
    global_api_server_thread.start()

    client_server_thread = threading.Thread(
        target=lambda: client_frontend_app.run(
            host="0.0.0.0", port=FLASK_CLIENT_PORT, debug=False, use_reloader=False
        ),
        daemon=True
    )
    client_server_thread.start()

    device_name = f"StageBridge-{socket.gethostname()}"
    start_discovery_service(port=FLASK_API_PORT, device_name=device_name)

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        stream=sys.stdout
    )

if __name__ == "__main__":
    threading.Thread(target=start_all_services, daemon=True).start()
    StageBridgeApp().run()