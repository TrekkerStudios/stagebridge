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

def _osc_handler(address, *args):
    """Handles incoming OSC messages and translates them to physical MIDI."""
    print(f"OSC Received: {address} {args}")
    
    # Check for predefined mappings first
    mapping_found = False
    for mapping in shared_state.config.get("osc_mappings", []):
        if mapping["osc_address"] == address:
            mapping_found = True
            
            if not shared_state.midi_out_port:
                print("Warning: MIDI output port not configured or open.")
                continue
            
            midi_sequence = mapping.get("midi_sequence", [])
            if not midi_sequence: 
                continue
            
            print(f"Found mapping for {address}. Sending sequence...")
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
                    print(f"Error processing step in sequence for {address}: {e}")
    
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