# discovery.py
import socket
import threading
import time
from zeroconf import ServiceInfo, Zeroconf

def get_ip_address():
    """Gets the primary IP address of the device."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Doesn't have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

def start_discovery_service(port, device_name="StageBridge"):
    """Starts the Zeroconf service announcement in a background thread."""
    
    def run_zeroconf():
        ip_address = get_ip_address()
        
        # A unique name for this specific device instance on the network
        instance_name = f"{device_name}._stagebridge-api._tcp.local."
        
        # The service type that your dashboard will search for
        service_type = "_stagebridge-api._tcp.local."
        
        # Information about the service being advertised
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
        
        try:
            # The service will be announced until the program is stopped
            while True:
                time.sleep(0.1)
        finally:
            print("Zeroconf: Unregistering service.")
            zeroconf.unregister_service(service_info)
            zeroconf.close()

    # Run the Zeroconf logic in a daemon thread so it doesn't block the main app
    discovery_thread = threading.Thread(target=run_zeroconf, daemon=True)
    discovery_thread.start()
    print("Zeroconf discovery service thread started.")