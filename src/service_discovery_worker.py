from PyQt6.QtCore import QThread, pyqtSignal
import socket
from zeroconf import Zeroconf, ServiceBrowser, ServiceListener

class DeviceDiscoveryWorker(QThread):
    device_found = pyqtSignal(str, str)  # name, ip
    device_removed = pyqtSignal(str, str)  # name, ip
    device_updated = pyqtSignal(str, str)  # name, ip
    log = pyqtSignal(str)

    def __init__(self, service="_ftp._tcp.local."):
        super().__init__()
        self.service = service
        self._stop = False
        self.zeroconf = None
        self.browser = None
        self.ip_list = set()
        self.name_list = set()

    def run(self):
        self.log.emit("Starting long-running device discovery using mDNS/zeroconf...")
        self.zeroconf = Zeroconf()
        self_outer = self
        class MyListener(ServiceListener):
            def add_service(self, zc, type_, name):
                self_outer.log.emit(f"Service found: {name}")
                info = zc.get_service_info(type_, name)
                if info and info.addresses:
                    txt_records = info.properties
                    found = False
                    if txt_records:
                        for k, v in txt_records.items():
                            val = v.decode() if isinstance(v, bytes) else v
                            if (b"MiniDexed" in k or b"MiniDexed" in v) or ("MiniDexed" in str(k) or "MiniDexed" in str(val)):
                                found = True
                                break
                    if found:
                        ip = socket.inet_ntoa(info.addresses[0])
                        name_str = info.server.rstrip('.')
                        if ip not in self_outer.ip_list:
                            self_outer.ip_list.add(ip)
                            self_outer.name_list.add(name_str)
                            self_outer.log.emit(f"Found MiniDexed device: {name_str} ({ip})")
                            self_outer.device_found.emit(name_str, ip)
            def remove_service(self, zc, type_, name):
                info = zc.get_service_info(type_, name)
                if info and info.addresses:
                    ip = socket.inet_ntoa(info.addresses[0])
                    name_str = info.server.rstrip('.')
                    if ip in self_outer.ip_list:
                        self_outer.ip_list.remove(ip)
                        self_outer.name_list.remove(name_str)
                        self_outer.log.emit(f"Device removed: {name_str} ({ip})")
                        self_outer.device_removed.emit(name_str, ip)
            def update_service(self, zc, type_, name):
                info = zc.get_service_info(type_, name)
                if info and info.addresses:
                    ip = socket.inet_ntoa(info.addresses[0])
                    name_str = info.server.rstrip('.')
                    self_outer.log.emit(f"Device updated: {name_str} ({ip})")
                    self_outer.device_updated.emit(name_str, ip)
        listener = MyListener()
        self.browser = ServiceBrowser(self.zeroconf, self.service, listener)
        try:
            self.exec()  # Run event loop until thread is stopped
        finally:
            self.zeroconf.close()
