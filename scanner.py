import threading
import time
from models import Device, ScanResult
from datetime import datetime
from itertools import chain

from scapy.layers.l2 import Ether, ARP
from scapy.config import conf
from scapy.sendrecv import srp

from multiprocessing import Process, Queue


def arp_scan(queue, subnet, interface):
    conf.verb = 0
    ans, uan = srp(Ether(dst="ff:ff:ff:ff:ff:ff") / ARP(pdst=subnet), timeout=10, iface=interface, retry=3)

    for snd, rcv in ans:
        mac_addr = rcv.sprintf("%Ether.src%")
        ip_addr = rcv.sprintf("%ARP.psrc%")

        queue.put((mac_addr, ip_addr))


class LanScanner:
    def __init__(self, interval, interface, subnet):
        self.last_scan = None
        self.new_device_alert = None
        self.known_devices = []

        self.scan_interval = interval
        self.interface = interface
        self.subnet = subnet

    def arp_scan(self):
        queue = Queue()
        p = Process(target=arp_scan, args=(queue, self.subnet, self.interface))
        start_time = time.time()
        p.start()
        p.join()
        end_time = time.time()

        if end_time - start_time > self.scan_interval:
            print("WARNING: Scan was longer than interval. Sequent scans can overlap and cause CPU overloading.")

        self.last_scan = timestamp = datetime.now()

        devices = [d for d in Device.select()]

        while not queue.empty():
            mac_addr, ip_addr = queue.get()

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
