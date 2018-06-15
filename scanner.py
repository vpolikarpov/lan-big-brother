import threading
from models import Device, ScanResult
from scapy.all import *
from datetime import datetime


class LanScanner:
    def __init__(self):
        self.last_scan = None

    def arp_scan(self, interface, ips):
        conf.verb = 0

        ans, _ = srp(Ether(dst="ff:ff:ff:ff:ff:ff") / ARP(pdst=ips), timeout=2, iface=interface, inter=0.1)

        self.last_scan = timestamp = datetime.now()

        for snd, rcv in ans:
            mac_addr = rcv.sprintf("%Ether.src%")
            ip_addr = rcv.sprintf("%ARP.psrc%")

            try:
                device = Device.get(Device.mac_addr == mac_addr)
            except Device.DoesNotExist:
                device = None

            ScanResult(time=timestamp, device=device, mac_addr=mac_addr, ip_addr=ip_addr).save()

    def start_scan(self, interval, interface, subnet):
        threading.Timer(interval, self.start_scan, [interval, interface, subnet]).start()

        self.arp_scan(interface, subnet)


lan_scanner = LanScanner()
