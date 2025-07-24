import threading
import time
from mido import Message, get_input_names, get_output_names, open_input, open_output
import shared_state

def initialize_ports():
    config = shared_state.config
    try:
        if config.get("midi_input_name"):
            shared_state.midi_in_port = open_input(config["midi_input_name"])
        if config.get("midi_output_name"):
            shared_state.midi_out_port = open_output(config["midi_output_name"])
        if config.get("rtp_midi_target_ip") and config.get("rtp_midi_target_port"):
            rtp_ip, rtp_port = config["rtp_midi_target_ip"], config["rtp_midi_target_port"]
            shared_state.rtp_midi_port = open_output(name=None, client=True, host=rtp_ip, port=rtp_port)
    except Exception as e:
        print(f"MIDI port error: {e}")

def _send_rtp_midi(midi_message):
    if shared_state.rtp_midi_port:
        try:
            shared_state.rtp_midi_port.send(midi_message)
        except Exception as e:
            print(f"RTP-MIDI error: {e}")

def _midi_input_thread_func():
    if not shared_state.midi_in_port:
        return
    while True:
        for msg in shared_state.midi_in_port.iter_pending():
            _send_rtp_midi(msg)
        time.sleep(0.001)

def start_midi_passthrough():
    threading.Thread(target=_midi_input_thread_func, daemon=True).start()