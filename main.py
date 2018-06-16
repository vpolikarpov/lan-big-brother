#!/usr/bin/python3

import os
import yaml, re
from datetime import datetime

from bot import TelegramBot, BotState
from models import Person, Device, ScanResult
from peewee import fn, JOIN
from scanner import lan_scanner


def format_datetime(dt):
    now = datetime.now()
    interval = now - dt
    if interval.days < 180:
        return dt.strftime("%d %b, %H:%M")
    else:
        return dt.strftime("%d %b %Y")


CMD_CANCEL = "Cancel"
CMD_WHO_NOW = "Who"
CMD_HISTORY = "Last"
CMD_ADD_PERSON = "Add person"
CMD_ADD_DEVICE = "Add device"


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
        self.chat.reply("Работаем", new_state=BotMainState)

    def get_conn_devices(self):
        all_results = ScanResult\
            .filter(ScanResult.time == lan_scanner.last_scan)\
            .join(Device, JOIN.LEFT_OUTER)
        anon_results = []

        msg_text = "Результаты на %s\n" % lan_scanner.last_scan.strftime("%Y.%m.%d %X")

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

        self.chat.reply(
            msg_text,
            parse_mode='HTML',
        )

    def get_last_devices(self):
        all_results = ScanResult\
            .select()\
            .join(Device, JOIN.LEFT_OUTER)\
            .group_by(ScanResult.mac_addr)\
            .having(fn.Max(ScanResult.time) == ScanResult.time)\
            .order_by(-ScanResult.time)

        anon_results = []

        msg_text = "Результаты на %s\n" % lan_scanner.last_scan.strftime("%Y.%m.%d %X")

        if len(all_results) > 0:
            msg_text += "\nПользователи:\n"
            for r in all_results:
                if r.device:
                    d = r.device
                    msg_text += "%s: %s (%s) \n" % (
                        format_datetime(r.time),
                        d.owner.name if d.owner else "<b>Кто-то</b>",
                        d.name or "<b>N/A</b>"
                    )
                else:
                    anon_results.append(r)

        if len(anon_results) > 0:
            msg_text += "\nНеизвестные устройства:\n<code>"
            for r in anon_results:
                msg_text += "%s - %s\n" % (format_datetime(r.time), r.mac_addr)
            msg_text += "</code>"

        self.chat.reply(
            msg_text,
            parse_mode='HTML',
        )

    def add_person(self):
        self.chat.reply(
            "User registration.\nPlease, enter user name:",
            new_state=BotAddPersonState,
        )

    def add_device(self):
        self.chat.reply(
            "Device registration.\nPlease, enter MAC address:",
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
            match = re.fullmatch('([0-9a-f]{2}:){6}', text + ":")
            if match:
                self.mac_addr = text
                self.chat.reply("Enter the device name:")
            else:
                self.chat.reply("It's not a MAC address. Try again:")
        elif self.name is None:
            self.name = text
            self.chat.reply("Enter owner's name:")
        else:
            try:
                owner = Person.get(Person.name == text)
                Device(mac_addr=self.mac_addr, name=self.name, owner=owner).save()
                self.chat.reply(
                    "Device registered",
                    new_state=BotMainState,
                )
            except Person.DoesNotExist:
                self.chat.reply("Person not found. Try again:")

    def cancel(self):
        self.chat.reply(
            "Registration canceled",
            new_state=BotMainState,
        )


if __name__ == "__main__":

    with open(os.path.join(os.path.dirname(__file__), 'lanwatcher.yml')) as f:
        settings = yaml.load(f.read())
        TOKEN = settings["bot_token"]
        ADMIN_CHAT = settings["admin_chat"]
        INTERVAL = settings["scan_interval"]
        INTERFACE = settings["interface"]
        SUBNET = settings["subnet"]

    bot = TelegramBot(TOKEN, BotMainState)
    bot.allow_chat(ADMIN_CHAT)
    print("Bot started")

    lan_scanner.start_scan(INTERVAL, INTERFACE, SUBNET)
    print("Scan started")
