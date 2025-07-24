import threading
import time
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import ThreadingOSCUDPServer
from pythonosc import udp_client
from mido import Message
import shared_state

def _relay_to_discovered_devices(address, *args):
    """Relays OSC message to all discovered StageBridge devices."""
    if not shared_state.discovered_devices:
        print("No discovered devices to relay to")
        return
    
    print(f"Relaying OSC message {address} {args} to {len(shared_state.discovered_devices)} devices")
    
    for device_name, device_info in shared_state.discovered_devices.items():
        try:
            # Create client on-demand
            client = udp_client.SimpleUDPClient(
                device_info['ip'], 
                shared_state.config.get('osc_server_port', 9000)
            )
            client.send_message(address, args)
            print(f"  -> Relayed to {device_info['name']} ({device_info['ip']})")
        except Exception as e:
            print(f"  -> Failed to relay to {device_info['name']}: {e}")

def _relay_to_broadcast(address, *args):
    """Relays OSC message to broadcast address."""
    broadcast_ip = shared_state.config.get('osc_broadcast_ip', '0.0.0.0')
    broadcast_port = shared_state.config.get('osc_broadcast_port', 9000)
    
    try:
        client = udp_client.SimpleUDPClient(broadcast_ip, broadcast_port)
        client.send_message(address, args)
        print(f"Relayed OSC message {address} {args} to {broadcast_ip}:{broadcast_port}")
    except Exception as e:
        print(f"Failed to relay to broadcast address {broadcast_ip}:{broadcast_port}: {e}")

def _send_local_osc_sequence(osc_sequence):
    """Sends a sequence of OSC messages locally."""
    local_port = shared_state.config.get('osc_server_port', 9000)
    
    try:
        # Create a client to send to ourselves (localhost)
        local_client = udp_client.SimpleUDPClient('127.0.0.1', local_port)
        
        for osc_command in osc_sequence:
            address = osc_command.get('address')
            args = osc_command.get('args', [])
            
            if address:
                print(f"  -> Sending local OSC: {address} {args}")
                local_client.send_message(address, args)
                time.sleep(0.01)  # Small delay between commands
                
    except Exception as e:
        print(f"Error sending local OSC sequence: {e}")

def _osc_handler(address, *args):
    """Handles incoming OSC messages and translates them to MIDI or OSC."""
    print(f"OSC Received: {address} {args}")
    
    # Check for predefined mappings first
    mapping_found = False
    for mapping in shared_state.config.get("osc_mappings", []):
        if mapping["osc_address"] == address:
            mapping_found = True
            mapping_type = mapping.get("mapping_type", "midi")
            
            if mapping_type == "osc":
                # Handle OSC-to-OSC mapping
                osc_sequence = mapping.get("osc_sequence", [])
                if osc_sequence:
                    print(f"Found OSC mapping for {address}. Sending OSC sequence...")
                    _send_local_osc_sequence(osc_sequence)
                    
            else:
                # Handle OSC-to-MIDI mapping (existing code)
                if not shared_state.midi_out_port:
                    print("Warning: MIDI output port not configured or open.")
                    continue
                
                midi_sequence = mapping.get("midi_sequence", [])
                if not midi_sequence: 
                    continue
                
                print(f"Found MIDI mapping for {address}. Sending MIDI sequence...")
                for midi_info in midi_sequence:
                    try:
                        msg_type = midi_info["type"]
                        channel = int(midi_info["channel"])
                        
                        if msg_type == "program_change":
                            msg = Message("program_change", channel=channel, program=int(midi_info["program"]))
                        elif msg_type == "control_change":
                            msg = Message("control_change", channel=channel, control=int(midi_info["control"]), value=int(midi_info["value"]))
                        else: 
                            continue
                        
                        print(f"  -> Sending MIDI: {msg}")
                        shared_state.midi_out_port.send(msg)
                        time.sleep(0.01)
                    except Exception as e:
                        print(f"Error processing step in MIDI sequence for {address}: {e}")
    
    # If no mapping found, relay based on mode
    if not mapping_found:
        relay_mode = shared_state.config.get('osc_relay_mode', 'zeroconf')
        
        if relay_mode == 'broadcast':
            print(f"No mapping found for {address}, relaying to broadcast address")
            _relay_to_broadcast(address, *args)
        else:  # zeroconf mode
            print(f"No mapping found for {address}, relaying to discovered devices")
            _relay_to_discovered_devices(address, *args)

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