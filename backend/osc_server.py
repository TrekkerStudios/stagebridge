# osc_server.py
import threading
import time
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import ThreadingOSCUDPServer
from mido import Message
import shared_state

def _osc_handler(address, *args):
    """Handles incoming OSC messages and translates them to physical MIDI."""
    print(f"OSC Received: {address} {args}")
    if not shared_state.midi_out_port:
        print("Warning: MIDI output port not configured or open.")
        return
    
    for mapping in shared_state.config.get("osc_mappings", []):
        if mapping["osc_address"] == address:
            midi_sequence = mapping.get("midi_sequence", [])
            if not midi_sequence: continue
            
            print(f"Found mapping for {address}. Sending sequence...")
            for midi_info in midi_sequence:
                try:
                    msg_type = midi_info["type"]
                    # channel = int(midi_info["channel"]) - 1
                    channel = int(midi_info["channel"])
                    if msg_type == "program_change":
                        msg = Message("program_change", channel=channel, program=int(midi_info["program"]))
                    elif msg_type == "control_change":
                        msg = Message("control_change", channel=channel, control=int(midi_info["control"]), value=int(midi_info["value"]))
                    else: continue
                    
                    print(f"  -> Sending MIDI: {msg}")
                    shared_state.midi_out_port.send(msg)
                    time.sleep(0.01) # Small delay for reliability
                except Exception as e:
                    print(f"Error processing step in sequence for {address}: {e}")

def start_osc_server():
    """Starts the OSC server in a background thread."""
    config = shared_state.config
    dispatcher = Dispatcher()
    dispatcher.set_default_handler(_osc_handler)
    
    osc_server = ThreadingOSCUDPServer(
        (config["osc_server_ip"], config["osc_server_port"]), dispatcher
    )
    
    osc_thread = threading.Thread(target=osc_server.serve_forever, daemon=True)
    osc_thread.start()
    print(f"OSC Server listening on {osc_server.server_address}")