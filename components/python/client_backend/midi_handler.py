# midi_handler.py
import threading
import time
from mido import Message, get_input_names, get_output_names, open_input, open_output
import shared_state

def initialize_ports():
    """Initializes all physical and network MIDI ports based on the config."""
    config = shared_state.config
    try:
        # Open local physical MIDI ports
        if config.get("midi_input_name"):
            print(f"Attempting to open MIDI Input: {config['midi_input_name']}")
            shared_state.midi_in_port = open_input(config["midi_input_name"])
            print(f"Successfully opened MIDI Input: {shared_state.midi_in_port.name}")
        if config.get("midi_output_name"):
            print(f"Attempting to open MIDI Output: {config['midi_output_name']}")
            shared_state.midi_out_port = open_output(config["midi_output_name"])
            print(f"Successfully opened MIDI Output: {shared_state.midi_out_port.name}")

        # Initialize RTP-MIDI Output Port using mido's built-in functionality
        if config.get("rtp_midi_target_ip") and config.get("rtp_midi_target_port"):
            rtp_ip, rtp_port = config["rtp_midi_target_ip"], config["rtp_midi_target_port"]
            print(f"Attempting to open RTP-MIDI Output to {rtp_ip}:{rtp_port}")
            shared_state.rtp_midi_port = open_output(name=None, client=True, host=rtp_ip, port=rtp_port)
            print(f"Successfully opened RTP-MIDI Output to {rtp_ip}:{rtp_port}")
    except Exception as e:
        print(f"ERROR: Could not open MIDI ports: {e}")

def _send_rtp_midi(midi_message):
    """Internal function to send a message via the RTP-MIDI port."""
    if not shared_state.rtp_midi_port:
        return
    try:
        shared_state.rtp_midi_port.send(midi_message)
        print(f"RTP-MIDI Sent: {midi_message}")
    except Exception as e:
        print(f"Error sending RTP-MIDI message: {e}")

def _midi_input_thread_func():
    """The function that runs in a thread, listening for physical MIDI input."""
    print("Starting MIDI input listener...")
    if not shared_state.midi_in_port:
        print("MIDI Input not configured. RTP-MIDI passthrough is disabled.")
        return
    while True:
        for msg in shared_state.midi_in_port.iter_pending():
            print(f"MIDI In: {msg} -> Sending via RTP-MIDI")
            _send_rtp_midi(msg)
        time.sleep(0.001)

def start_midi_passthrough():
    """Starts the MIDI passthrough thread."""
    midi_thread = threading.Thread(target=_midi_input_thread_func, daemon=True)
    midi_thread.start()