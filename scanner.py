import threading
from models import Device, ScanResult
from itertools import chain
from datetime import datetime


class AbstractScanner:
    def __init__(self, interval):
        self.last_scan = None
        self.new_device_alert = None
        self.known_devices = []
        self._registered_devices = []

        self.scan_interval = interval

    def scan(self):
        raise NotImplemented

    def cycle_scan(self):
        threading.Timer(self.scan_interval, self.cycle_scan).start()

        self._registered_devices = [d for d in Device.select()]
        self.scan()

    def start_scan(self):
        results = ScanResult.select(ScanResult.mac_addr).distinct()
        devices = Device.select(Device.mac_addr).distinct()
        for r in chain(results, devices):
            if r.mac_addr not in self.known_devices:
                self.known_devices.append(r.mac_addr)

        self.cycle_scan()

    def add_scan_result(self, mac_addr_raw, ip_addr, timestamp=None):
        mac_addr = mac_addr_raw.lower().replace("-", ":")
        device = None
        for d in self._registered_devices:
            if d.mac_addr == mac_addr:
                device = d
                break

        ScanResult(time=(timestamp or datetime.now()), device=device, mac_addr=mac_addr, ip_addr=ip_addr).save()

        if mac_addr not in self.known_devices:
            self.known_devices.append(mac_addr)
            if self.new_device_alert is not None:
                self.new_device_alert(mac_addr)

    def set_new_device_alert(self, fn):
        self.new_device_alert = fn
