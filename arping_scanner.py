import time
from datetime import datetime

from scanner import AbstractScanner

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


class ARPScanner(AbstractScanner):
    def __init__(self, interval, interface, subnet):
        super().__init__(interval)
        self.interface = interface
        self.subnet = subnet

    def scan(self):
        queue = Queue()
        p = Process(target=arp_scan, args=(queue, self.subnet, self.interface))
        start_time = time.time()
        p.start()
        p.join()
        end_time = time.time()

        if end_time - start_time > self.scan_interval:
            print("WARNING: Scan was longer than interval. Sequent scans can overlap and cause CPU overloading.")

        self.last_scan = timestamp = datetime.now()

        while not queue.empty():
            mac_addr, ip_addr = queue.get()
            self.add_scan_result(mac_addr, ip_addr, timestamp)
