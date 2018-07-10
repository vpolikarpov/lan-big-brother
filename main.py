#!/usr/bin/python3

import os
import re
import yaml
from datetime import datetime
from itertools import groupby


from bot import TelegramBot, BotState, KeyboardMarkup
from models import Person, Device, ScanResult
from peewee import fn, JOIN
from scanner import LanScanner


def format_datetime(dt):
    now = datetime.now()
    interval = (now.date() - dt.date()).days
    if interval < 1:
        return dt.strftime("%H:%M")
    elif interval < 7:
        return dt.strftime("%a, %H:%M")
    elif interval < 180:
        return dt.strftime("%d %b, %H:%M")
    else:
        return dt.strftime("%d %b %Y")


CMD_CANCEL = "Cancel"
CMD_WHO_NOW = "Who"
CMD_HISTORY = "Last"
CMD_ADD_PERSON = "Add person"
CMD_ADD_DEVICE = "Add device"
CMD_REGISTER = "➕ Register"


class BotMainState(BotState):

    commands = {
        '/start': "start",
    }

    buttons = [
        {
            CMD_WHO_NOW: "get_conn_devices",
            CMD_HISTORY: "get_last_devices",
        },
        {
            CMD_ADD_PERSON: "add_person",
            CMD_ADD_DEVICE: "add_device",
        }
    ]

    def start(self, _):
        self.chat.reply("It works", new_state=BotMainState)

    def get_conn_devices(self):
        if lan_scanner.last_scan is None:
            self.chat.reply("Scanner is not started yet")
            return

        all_results = ScanResult\
            .filter(ScanResult.time == lan_scanner.last_scan)\
            .join(Device, JOIN.LEFT_OUTER)
        anon_results = []

        msg_text = "Connected devices as of %s\n" % lan_scanner.last_scan.strftime("%Y.%m.%d %X")

        if len(all_results) > 0:
            msg_text += "\nKnown devices:\n"
            for r in all_results:
                if r.device:
                    d = r.device
                    msg_text += "%s: %s\n" % (d.owner.name if d.owner else "<b>N/A</b>", d.name or "<b>N/A</b>")
                else:
                    anon_results.append(r)

        if len(anon_results) > 0:
            msg_text += "\nUnknown devices:\n<code>"
            for r in anon_results:
                msg_text += "%s %s\n" % (r.mac_addr, r.ip_addr)
            msg_text += "</code>"

        self.chat.reply(
            msg_text,
            parse_mode='HTML',
        )

    def get_last_devices(self):
        if lan_scanner.last_scan is None:
            self.chat.reply("Scanner is not started yet")
            return

        results = ScanResult\
            .select()\
            .join(Device, JOIN.LEFT_OUTER)\
            .group_by(ScanResult.mac_addr)\
            .having(fn.Max(ScanResult.time) == ScanResult.time)\
            .order_by(-ScanResult.time)

        now = datetime.now()
        for r in results:
            interval = (now.date() - r.time.date()).days
            if interval >= 7:
                r.interval_readable = "Long time ago"
            elif interval >= 2:
                r.interval_readable = "Last week"
            elif interval >= 1:
                r.interval_readable = "Yesterday"
            else:
                r.interval_readable = "Today"

        msg_text = "Recent active devices list\nAs of %s\n" % lan_scanner.last_scan.strftime("%Y.%m.%d %X")

        for k, g in groupby(results, lambda x: x.interval_readable):
            msg_text += "\n<b>%s</b>\n" % k
            for r in g:
                if r.device:
                    d = r.device
                    msg_text += "%s: %s (%s) \n" % (
                        format_datetime(r.time),
                        d.owner.name if d.owner else "N/A",
                        d.name or "N/A"
                    )
                else:
                    msg_text += "%s: <code>%s</code>\n" % (format_datetime(r.time), r.mac_addr)

        self.chat.reply(
            msg_text,
            parse_mode='HTML',
        )

    def add_person(self):
        self.chat.reply(
            "User registration.\nPlease, send me the name.",
            new_state=BotAddPersonState,
        )

    def add_device(self):
        self.chat.reply(
            "Device registration.\nPlease, send me the MAC address. It's recommended to enclose it in grave accents "
            "(`) to prevent emoji appearance.",
            new_state=BotAddDeviceState,
        )


class BotAddPersonState(BotState):

    buttons = [{CMD_CANCEL: "cancel"}]

    def default(self, text):
        Person(name=text).save()
        self.chat.reply(
            "Person registered",
            new_state=BotMainState,
        )

    def cancel(self):
        self.chat.reply(
            "Registration canceled",
            new_state=BotMainState,
        )


class BotAddDeviceState(BotState):
    buttons = [{CMD_CANCEL: "cancel"}]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mac_addr = None
        self.name = None

    def default(self, text):
        if self.mac_addr is None:
            match = re.fullmatch('([0-9a-fA-F]{2}[:-]){6}', text + ":")
            if match:
                self.mac_addr = text.lower().replace("-", ":")
                self.chat.reply("Ok, now enter device name.")
            else:
                self.chat.reply("It's not a valid MAC address. Valid MAC address consists of six 8-bit "
                                "hexadecimal numbers joined with colons or hyphens.")
        elif self.name is None:
            self.name = text
            self.chat.reply("Finally, enter person's name, who owns this device.")
        else:
            try:
                owner = Person.get(Person.name == text)
                dev = Device(mac_addr=self.mac_addr, name=self.name, owner=owner)
                dev.save()
                ScanResult.update(device=dev).where(ScanResult.mac_addr == self.mac_addr).execute()
                self.chat.reply(
                    "Device registered",
                    new_state=BotMainState,
                )
            except Person.DoesNotExist:
                self.chat.reply("I don't know anybody with such name. Try again.")

    def cancel(self):
        self.chat.reply(
            "Registration canceled",
            new_state=BotMainState,
        )


class NewDeviceAlertMarkup(KeyboardMarkup):
    buttons = [{
        CMD_REGISTER: "register",
    }]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mac_addr = None

    def register(self, _):
        # TODO: Prevent multi registration
        # msg_pointer = (query['message']['chat']['id'], query['message']['message_id'])

        self.chat.reply(
            "Device registration\nEnter device name",
            new_state=BotAddDeviceState,
            state_kwargs={"mac_addr": self.mac_addr}
        )


def new_device_alert(mac_addr):
    markup = NewDeviceAlertMarkup()
    markup.mac_addr = mac_addr

    bot.inline_all(
        "New device has been connected.\nMAC address: <code>%s</code>" % mac_addr,
        parse_mode='HTML',
        markup=markup,  # TODO: Тут лажа: в несколько чатов пихаем один инстанс
    )


if __name__ == "__main__":

    with open(os.path.join(os.path.dirname(__file__), 'lanwatcher.yml')) as f:
        settings = yaml.load(f.read())
        TOKEN = settings["bot_token"]
        ADMIN_CHAT = settings["admin_chat"]
        INTERVAL = settings["scan_interval"]
        INTERFACE = settings["interface"]
        SUBNET = settings["subnet"]

    lan_scanner = LanScanner(INTERVAL, INTERFACE, SUBNET)
    lan_scanner.set_new_device_alert(new_device_alert)

    bot = TelegramBot(TOKEN, BotMainState)
    bot.allow_chat(ADMIN_CHAT)
    print("Bot started")

    lan_scanner.start_scan()
    print("Scan started")
