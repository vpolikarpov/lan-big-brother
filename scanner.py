import threading
from models import Device, ScanResult
from datetime import datetime
from itertools import chain

from scapy.layers.l2 import Ether, ARP
from scapy.config import conf
from scapy.sendrecv import srp


class LanScanner:
    def __init__(self, interval, interface, subnet):
        self.last_scan = None
        self.new_device_alert = None
        self.known_devices = []

        self.scan_interval = interval
        self.interface = interface
        self.subnet = subnet

        self.payload = Ether(dst="ff:ff:ff:ff:ff:ff") / ARP(pdst=self.subnet)

    def arp_scan(self):
        conf.verb = 0

        ans, uan = srp(self.payload, timeout=10, iface=self.interface, retry=3)
        self.last_scan = timestamp = datetime.now()

        devices = [d for d in Device.select()]

        for snd, rcv in ans:
            mac_addr = rcv.sprintf("%Ether.src%")
            ip_addr = rcv.sprintf("%ARP.psrc%")

            device = None
            for d in devices:
                if d.mac_addr == mac_addr:
                    device = d
                    break

            ScanResult(time=timestamp, device=device, mac_addr=mac_addr, ip_addr=ip_addr).save()

            if mac_addr not in self.known_devices:
                self.known_devices.append(mac_addr)
                if self.new_device_alert is not None:
                    self.new_device_alert(mac_addr)

    def cycle_scan(self):
        threading.Timer(self.scan_interval, self.cycle_scan).start()
        self.arp_scan()

    def start_scan(self):
        results = ScanResult.select(ScanResult.mac_addr).distinct()
        devices = Device.select(Device.mac_addr).distinct()
        for r in chain(results, devices):
            if r.mac_addr not in self.known_devices:
                self.known_devices.append(r.mac_addr)

        self.cycle_scan()

    def set_new_device_alert(self, fn):
        self.new_device_alert = fn
