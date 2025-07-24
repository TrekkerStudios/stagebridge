import json
import shared_state

CONFIG_FILE = "config.json"

def load_config():
    try:
        with open(CONFIG_FILE, "r") as f:
            shared_state.config = json.load(f)
    except FileNotFoundError:
        shared_state.config = {
            "osc_server_ip": "0.0.0.0",
            "osc_server_port": 9000,
            "rtp_midi_target_ip": "192.168.1.100",
            "rtp_midi_target_port": 5004,
            "midi_input_name": None,
            "midi_output_name": None,
            "osc_relay_mode": "zeroconf",
            "osc_broadcast_ip": "0.0.0.0",
            "osc_broadcast_port": 9000,
            "song_parser_settings": {
                "column_name": "QUAD PATCH",
                "scene_prefix": "SC ",
                "footswitch_prefix": "FS ",
                "osc_prefix": "/patch",
            },
            "osc_mappings": [],
        }
        save_config()
    
    if "osc_relay_mode" not in shared_state.config:
        shared_state.config["osc_relay_mode"] = "zeroconf"
    if "osc_broadcast_ip" not in shared_state.config:
        shared_state.config["osc_broadcast_ip"] = "0.0.0.0"
    if "osc_broadcast_port" not in shared_state.config:
        shared_state.config["osc_broadcast_port"] = 9000

def save_config():
    with open(CONFIG_FILE, "w") as f:
        json.dump(shared_state.config, f, indent=2)