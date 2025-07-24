# config_manager.py
import json
import shared_state

CONFIG_FILE = "config.json"

def load_config():
    """Loads configuration from JSON file or creates a default one."""
    try:
        with open(CONFIG_FILE, "r") as f:
            shared_state.config = json.load(f)
    except FileNotFoundError:
        print(f"WARNING: {CONFIG_FILE} not found. Creating a default config.")
        shared_state.config = {
            "osc_server_ip": "0.0.0.0",
            "osc_server_port": 9000,
            "rtp_midi_target_ip": "192.168.1.100",
            "rtp_midi_target_port": 5004,
            "midi_input_name": None,
            "midi_output_name": None,
            "osc_relay_mode": "zeroconf",  # NEW
            "osc_broadcast_ip": "0.0.0.0",  # NEW
            "osc_broadcast_port": 9000,     # NEW
            "song_parser_settings": {
                "column_name": "QUAD PATCH",
                "scene_prefix": "SC ",
                "footswitch_prefix": "FS ",
                "osc_prefix": "/patch",
            },
            "osc_mappings": [],
        }
        save_config()
    
    # Ensure new settings exist for older configs
    if "osc_relay_mode" not in shared_state.config:
        shared_state.config["osc_relay_mode"] = "zeroconf"
    if "osc_broadcast_ip" not in shared_state.config:
        shared_state.config["osc_broadcast_ip"] = "0.0.0.0"
    if "osc_broadcast_port" not in shared_state.config:
        shared_state.config["osc_broadcast_port"] = 9000