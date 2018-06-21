from threading import Timer
from models import Device, ScanResult
from scapy.all import *
from datetime import datetime
from itertools import chain


class LanScanner:
    def __init__(self, interval, interface, subnet):
        self.last_scan = None
        self.new_device_alert = None
        self.known_devices = []

        self.scan_interval = interval
        self.interface = interface
        self.subnet = subnet

    def arp_scan(self, interface, ips):
        conf.verb = 0

        ans, _ = srp(Ether(dst="ff:ff:ff:ff:ff:ff") / ARP(pdst=ips), timeout=10, iface=interface, retry=3)

        self.last_scan = timestamp = datetime.now()

        for snd, rcv in ans:
            mac_addr = rcv.sprintf("%Ether.src%")
            ip_addr = rcv.sprintf("%ARP.psrc%")

            try:
                device = Device.get(Device.mac_addr == mac_addr)
            except Device.DoesNotExist:
                device = None

            ScanResult(time=timestamp, device=device, mac_addr=mac_addr, ip_addr=ip_addr).save()

            if mac_addr not in self.known_devices:
                self.known_devices.append(mac_addr)
                if self.new_device_alert is not None:
                    self.new_device_alert()

    def cycle_scan(self):
        Timer(self.scan_interval, self.cycle_scan).start()
        self.arp_scan(self.interface, self.subnet)

    def start_scan(self):
        results = ScanResult.select(ScanResult.mac_addr).distinct()
        devices = Device.select(Device.mac_addr).distinct()
        for r in chain(results, devices):
            if r.mac_addr not in self.known_devices:
                self.known_devices.append(r.mac_addr)

        self.cycle_scan()

    def set_new_device_alert(self, fn):
        self.new_device_alert = fn
