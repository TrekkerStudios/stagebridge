# shared_state.py
# This module holds the shared state of the application,
# allowing different components to access the same data and objects.

# The main configuration dictionary, loaded from config.json
config = {}

# Mido port objects
midi_in_port = None
midi_out_port = None
rtp_midi_port = None