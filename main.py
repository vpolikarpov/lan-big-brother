#!/usr/bin/python3

import sys
from datetime import datetime
from scapy.all import *
import threading


def arp_scan(iface, ips):
    start_time = datetime.now()
    conf.verb = 0

    ans, _ = srp(Ether(dst="ff:ff:ff:ff:ff:ff")/ARP(pdst=ips), timeout=2, iface=iface, inter=0.1)

    for snd, rcv in ans:
        print(rcv.sprintf("%Ether.src% - %ARP.psrc%"))

    stop_time = datetime.now()
    total_time = stop_time - start_time


def start_scan():
    threading.Timer(300, start_scan).start()

    arp_scan("eth0", "192.168.1.0/24")


start_scan()
