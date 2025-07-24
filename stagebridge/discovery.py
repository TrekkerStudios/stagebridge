import socket
import threading
import time
from zeroconf import ServiceInfo, Zeroconf, ServiceBrowser, ServiceListener
import shared_state
from pythonosc import udp_client

def get_ip_address():
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
    def add_service(self, zeroconf, type_, name):
        info = zeroconf.get_service_info(type_, name, timeout=3000)
        if info:
            ip_address = None
            if info.addresses:
                for addr_bytes in info.addresses:
                    try:
                        ip_address = socket.inet_ntoa(addr_bytes)
                        break
                    except OSError:
                        continue
            
            if ip_address and info.port:
                device_info = {
                    'name': info.properties.get(b'name', b'Unknown').decode('utf-8') if info.properties.get(b'name') else info.name,
                    'host': info.server,
                    'ip': ip_address,
                    'port': info.port,
                    'fqdn': info.server,
                    'client': udp_client.SimpleUDPClient(ip_address, shared_state.config.get('osc_server_port', 8000))
                }
                shared_state.discovered_devices[info.server] = device_info
    
    def remove_service(self, zeroconf, type_, name):
        info = zeroconf.get_service_info(type_, name)
        fqdn_to_remove = info.server if info else f"{name}.{type_}"
        
        if fqdn_to_remove in shared_state.discovered_devices:
            shared_state.discovered_devices.pop(fqdn_to_remove)
    
    def update_service(self, zeroconf, type_, name):
        pass

def start_discovery_service(port, device_name="StageBridge"):
    def run_zeroconf():
        try:
            ip_address = get_ip_address()
            
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
            
            # Create Zeroconf with interface restrictions to avoid network errors
            zeroconf = Zeroconf(interfaces=[ip_address])
            zeroconf.register_service(service_info)
            
            listener = StageBridgeListener()
            browser = ServiceBrowser(zeroconf, service_type, listener)
            
            try:
                while True:
                    time.sleep(1.0)  # Reduced frequency to minimize network traffic
            except KeyboardInterrupt:
                pass
            finally:
                try:
                    browser.cancel()
                    zeroconf.unregister_service(service_info)
                    zeroconf.close()
                except Exception:
                    pass  # Suppress cleanup errors
                    
        except Exception as e:
            print(f"Zeroconf discovery service error: {e}")

    discovery_thread = threading.Thread(target=run_zeroconf, daemon=True)
    discovery_thread.start()
    print("Zeroconf discovery service started.")