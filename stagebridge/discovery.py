import socket
import threading
import time
from zeroconf import ServiceInfo, Zeroconf, ServiceBrowser, ServiceListener
import shared_state
from pythonosc import udp_client

def get_ip_address():
    """Gets the primary IP address of the device."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

class StageBridgeListener(ServiceListener):
    """Listens for other StageBridge devices on the network."""
    
    def add_service(self, zeroconf, type_, name):
        info = zeroconf.get_service_info(type_, name, timeout=3000)
        if info:
            # Don't add ourselves
            our_ip = get_ip_address()
            
            ip_address = None
            if info.addresses:
                for addr_bytes in info.addresses:
                    try:
                        ip_address = socket.inet_ntoa(addr_bytes)
                        break
                    except OSError:
                        continue
            
            if ip_address and ip_address != our_ip and info.port:
                # Store in format expected by both OSC relay and fleet manager
                device_info = {
                    'name': info.properties.get(b'name', b'Unknown').decode('utf-8') if info.properties.get(b'name') else info.name,
                    'host': info.server,
                    'ip': ip_address,
                    'port': info.port,
                    'fqdn': info.server,
                    'client': udp_client.SimpleUDPClient(ip_address, shared_state.config.get('osc_server_port', 8000))
                }
                shared_state.discovered_devices[info.server] = device_info
                print(f"Discovered StageBridge device: {device_info['name']} at {ip_address}:{info.port}")
    
    def remove_service(self, zeroconf, type_, name):
        info = zeroconf.get_service_info(type_, name)
        fqdn_to_remove = info.server if info else f"{name}.{type_}"
        
        if fqdn_to_remove in shared_state.discovered_devices:
            device_info = shared_state.discovered_devices.pop(fqdn_to_remove)
            print(f"StageBridge device disconnected: {device_info['name']}")
        else:
            print(f"Device went away (not found in current list): {name}")
    
    def update_service(self, zeroconf, type_, name):
        pass

def start_discovery_service(port, device_name="StageBridge"):
    """Starts both Zeroconf service announcement and discovery in background threads."""
    
    def run_zeroconf():
        ip_address = get_ip_address()
        
        # Service announcement
        instance_name = f"{device_name}._stagebridge-api._tcp.local."
        service_type = "_stagebridge-api._tcp.local."
        
        service_info = ServiceInfo(
            type_=service_type,
            name=instance_name,
            addresses=[socket.inet_aton(ip_address)],
            port=port,
            properties={'name': device_name, 'version': '1.0'},
            server=f"{socket.gethostname().lower()}.local."
        )
        
        zeroconf = Zeroconf()
        print(f"Zeroconf: Registering service '{instance_name}' on {ip_address}:{port}")
        zeroconf.register_service(service_info)
        
        # Service discovery
        listener = StageBridgeListener()
        browser = ServiceBrowser(zeroconf, service_type, listener)
        print("Zeroconf: Started browsing for other StageBridge devices")
        
        try:
            while True:
                time.sleep(0.1)
        finally:
            print("Zeroconf: Unregistering service and stopping discovery.")
            browser.cancel()
            zeroconf.unregister_service(service_info)
            zeroconf.close()

    discovery_thread = threading.Thread(target=run_zeroconf, daemon=True)
    discovery_thread.start()
    print("Zeroconf discovery service thread started.")