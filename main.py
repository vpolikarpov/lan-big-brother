#!/usr/bin/python3

from datetime import datetime
from scapy.all import *
import yaml
import telepot
from telepot.loop import MessageLoop
from telepot.namedtuple import ReplyKeyboardMarkup, KeyboardButton
import threading
from models import Person, Device, ScanResult, JOIN_LEFT_OUTER


last_scan = None


def arp_scan(iface, ips):
    conf.verb = 0

    ans, _ = srp(Ether(dst="ff:ff:ff:ff:ff:ff")/ARP(pdst=ips), timeout=2, iface=iface, inter=0.1)

    global last_scan
    last_scan = timestamp = datetime.now()

    for snd, rcv in ans:
        mac_addr = rcv.sprintf("%Ether.src%")
        ip_addr = rcv.sprintf("%ARP.psrc%")

        try:
            device = Device.get(Device.mac_addr == mac_addr)
        except Device.DoesNotExist:
            device = None

        ScanResult(time=timestamp, device=device, mac_addr=mac_addr, ip_addr=ip_addr).save()


def start_scan():
    threading.Timer(INTERVAL, start_scan).start()

    arp_scan(INTERFACE, SUBNET)


########################


def cmd_start(chat_id, _):
    bot.sendMessage(chat_id, "Работаем",
                    reply_markup=ReplyKeyboardMarkup(keyboard=[
                        [
                            KeyboardButton(text="Устройства")
                        ]
                    ], resize_keyboard=True)
                    )


def cmd_get_conn_devices(chat_id, _):
    all_results = ScanResult.filter(ScanResult.time == last_scan).join(Device, JOIN_LEFT_OUTER)
    anon_results = []

    msg_text = "Результаты на %s\n" % last_scan.strftime("%H:%M:%S")

    if len(all_results) > 0:
        msg_text += "\nПользователи:\n"
        for r in all_results:
            if r.device:
                d = r.device
                msg_text += "%s: %s\n" % (d.owner.name if d.owner else "<b>Кто-то</b>", d.name or "<b>N/A</b>")
            else:
                anon_results.append(r)

    if len(anon_results) > 0:
        msg_text += "\nНеизвестные устройства:\n<code>"
        for r in anon_results:
            msg_text += "%s %s\n" % (r.mac_addr, r.ip_addr)
        msg_text += "</code>"

    bot.sendMessage(chat_id, msg_text, parse_mode='HTML')


def on_chat_message(msg):
    content_type, chat_type, chat_id = telepot.glance(msg)

    if chat_id != ADMIN_CHAT:
        bot.sendMessage(chat_id, "Ошибка доступа")
        return

    commands = {
        '/start': cmd_start,
        'Устройства': cmd_get_conn_devices,
    }

    if content_type == 'text':
        text = msg['text']

        cmd_args = text.split(" ")
        cmd_name = cmd_args.pop(0)

        func = commands.get(cmd_name)

        if func:
            func(chat_id, cmd_args)


if __name__ == "__main__":

    with open(os.path.join(os.path.dirname(__file__), 'lanwatcher.yml')) as f:
        settings = yaml.load(f.read())
        TOKEN = settings["bot_token"]
        ADMIN_CHAT = settings["admin_chat"]
        INTERVAL = settings["scan_interval"]
        INTERFACE = settings["interface"]
        SUBNET = settings["subnet"]

    start_scan()

    bot = telepot.Bot(TOKEN)
    MessageLoop(bot, {'chat': on_chat_message}).run_as_thread()

    print("Started")
