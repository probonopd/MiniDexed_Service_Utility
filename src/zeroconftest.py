# nuitka-project: --include-package=zeroconf

import site

site_ref = site

import sys
import logging
import traceback
import time
import platform
import importlib.metadata
from zeroconf import Zeroconf, ServiceBrowser
import os
import threading
import socket

logging.basicConfig(level=logging.DEBUG)
logging.getLogger("zeroconf").setLevel(logging.DEBUG)

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

def print_system_info() -> None:
    print("System Information:")
    print(f"  Platform: {platform.platform()}")
    print(f"  Python version: {platform.python_version()} ({sys.executable})")
    print(f"  Working directory: {os.getcwd()}")
    try:
        zeroconf_version = importlib.metadata.version('zeroconf')
    except Exception:
        zeroconf_version = 'unknown'
    print(f"  Zeroconf version: {zeroconf_version}")
    print(f"  Threading: active_count={threading.active_count()}, current_thread={threading.current_thread().name}")
    try:
        import selectors
        selector = selectors.DefaultSelector()
        print(f"  Selector: {selector.__class__.__name__}")
    except Exception as e:
        print(f"  Selector info error: {e}")
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(1)
        s.connect(("8.8.8.8", 80))
        print(f"  Outbound IP: {s.getsockname()[0]}")
        s.close()
    except Exception as e:
        print(f"  Outbound IP detection failed: {e}")
    print()


def log_threading_info(context: str) -> None:
    print(f"[Threading][{context}] active_count={threading.active_count()}, current_thread={threading.current_thread().name}")

class ServiceTypeListener:
    def __init__(self, zeroconf: Zeroconf) -> None:
        self.zeroconf: Zeroconf = zeroconf
        self.browsers: Dict[str, ServiceBrowser] = {}
        self.seen_types: Set[str] = set()
        log_threading_info("ServiceTypeListener.__init__")
    def add_service(self, zeroconf: Zeroconf, type: str, name: str) -> None:
        log_threading_info(f"ServiceTypeListener.add_service {name}")
        print(f"Service type {name} discovered.")
        try:
            if name not in self.seen_types:
                self.seen_types.add(name)
                self.browsers[name] = ServiceBrowser(zeroconf, name, ServiceInstanceListener(zeroconf, name))
        except Exception:
            print(f"Exception in ServiceTypeListener.add_service for {name}:")
            print(traceback.format_exc())
    def update_service(self, zeroconf: Zeroconf, type: str, name: str) -> None:
        log_threading_info(f"ServiceTypeListener.update_service {name}")
        try:
            pass
        except Exception:
            print(f"Exception in ServiceTypeListener.update_service for {name}:")
            print(traceback.format_exc())

class ServiceInstanceListener:
    def __init__(self, zeroconf: Zeroconf, type: str) -> None:
        self.zeroconf: Zeroconf = zeroconf
        self.type: str = type
        log_threading_info(f"ServiceInstanceListener.__init__ {type}")
    def add_service(self, zeroconf: Zeroconf, type: str, name: str) -> None:
        log_threading_info(f"ServiceInstanceListener.add_service {name}")
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
            print(traceback.format_exc())
    def remove_service(self, zeroconf: Zeroconf, type: str, name: str) -> None:
        log_threading_info(f"ServiceInstanceListener.remove_service {name}")
        print(f"  Instance {name} removed for type {type}")
        try:
            pass
        except Exception:
            print(f"Exception in ServiceInstanceListener.remove_service for {name}:")
            print(traceback.format_exc())
    def update_service(self, zeroconf: Zeroconf, type: str, name: str) -> None:
        log_threading_info(f"ServiceInstanceListener.update_service {name}")
        print(f"  Instance {name} updated for type {type}")
        try:
            pass
        except Exception:
            print(f"Exception in ServiceInstanceListener.update_service for {name}:")
            print(traceback.format_exc())

pywin32_refs = []
try:
    import pywin32_bootstrap
    pywin32_refs.append(pywin32_bootstrap)
except ImportError:
    pass
try:
    import pywin32_system32
    pywin32_refs.append(pywin32_system32)
except ImportError:
    pass

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
        with open("imported_modules.txt", "w") as f:
            for name in sorted(sys.modules):
                f.write(name + "\n")

if __name__ == "__main__":
    main()
