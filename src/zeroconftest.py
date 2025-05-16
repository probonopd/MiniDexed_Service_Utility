# nuitka-project: --include-module=zeroconf._handlers.answers
# nuitka-project: --include-module=zeroconf._utils.ipaddress
# nuitka-project: --include-package=zeroconf
# nuitka-project: --include-package=zeroconf._protocol
# nuitka-project: --include-package=zeroconf._services
# nuitka-project: --include-package=zeroconf._dns
# nuitka-project: --include-package=zeroconf._listener
# nuitka-project: --include-package=zeroconf._record_update
# nuitka-project: --include-package=zeroconf._updates
# nuitka-project: --include-package=zeroconf._history
# nuitka-project: --include-package=zeroconf._utils

import sys
sys.flags.verbose = 1
import time
import platform
import importlib.metadata
from zeroconf import Zeroconf, ServiceBrowser

try:
    import msvcrt  # Windows
    def key_pressed():
        return msvcrt.kbhit()
except ImportError:
    import select
    import sys
    def key_pressed():
        dr, dw, de = select.select([sys.stdin], [], [], 0)
        return dr != []

try:
    import zeroconf._protocol.incoming
    import zeroconf._protocol.outgoing
    import zeroconf._dns
    import zeroconf._listener
    import zeroconf._services
    import zeroconf._record_update
    print("All zeroconf submodules successfully imported.")
except ImportError as e:
    print(f"Missing submodule: {e}")

def print_system_info():
    print("System Information:")
    print(f"  Platform: {platform.platform()}")
    print(f"  Python version: {platform.python_version()} ({sys.executable})")
    try:
        zeroconf_version = importlib.metadata.version('zeroconf')
    except Exception:
        zeroconf_version = 'unknown'
    print(f"  Zeroconf version: {zeroconf_version}")
    print()

class ServiceTypeListener:
    def __init__(self, zeroconf):
        self.zeroconf = zeroconf
        self.browsers = {}
        self.seen_types = set()
    def add_service(self, zeroconf, type, name):
        print(f"Service type {name} discovered.")
        if name not in self.seen_types:
            self.seen_types.add(name)
            self.browsers[name] = ServiceBrowser(zeroconf, name, ServiceInstanceListener(zeroconf, name))
    def update_service(self, zeroconf, type, name):
        pass

class ServiceInstanceListener:
    def __init__(self, zeroconf, type):
        self.zeroconf = zeroconf
        self.type = type
    def add_service(self, zeroconf, type, name):
        print(f"  Instance {name} found for type {type}")
        try:
            info = zeroconf.get_service_info(type, name)
            if info:
                print(f"    Address: {info.parsed_addresses()}")
                print(f"    Port: {info.port}")
                print(f"    Server: {info.server}")
                print(f"    Properties: {info.properties}")
            else:
                print("    (No further info available)")
        except Exception as e:
            print(f"    (Error retrieving service info: {e})")
    def remove_service(self, zeroconf, type, name):
        print(f"  Instance {name} removed for type {type}")
    def update_service(self, zeroconf, type, name):
        print(f"  Instance {name} updated for type {type}")

def main():
    print_system_info()
    zeroconf = Zeroconf()
    type_listener = ServiceTypeListener(zeroconf)
    type_browser = ServiceBrowser(zeroconf, "_services._dns-sd._udp.local.", type_listener)
    print("Browsing for Zeroconf services. Press any key to exit.")
    try:
        while True:
            if key_pressed():
                break
            time.sleep(0.1)
    finally:
        zeroconf.close()
        print("Zeroconf browser stopped.")

if __name__ == "__main__":
    main()
