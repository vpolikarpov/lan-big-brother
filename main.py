#!/usr/bin/python3

import os
import re
import yaml
import ssl
from datetime import datetime, timedelta
from itertools import groupby
from time import sleep

from telepot.namedtuple import InlineQueryResultArticle
from bot import TelegramBot, BotState, InlineKeyboard

from models import Person, Device, ScanResult
from peewee import fn, JOIN, SQL, NodeList
from arping_scanner import ARPScanner
from routeros_scanner import RouterOsScanner


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
CMD_WHO_NOW = "Current"
CMD_LAST1H = "Last hour"
CMD_HISTORY = "Full history"
CMD_ADD_PERSON = "Add person"
CMD_ADD_DEVICE = "Add device"
CMD_REGISTER = "➕ Register"
CMD_SEARCH = "🔍 Search"


class BotMainState(BotState):

    commands = {
        '/start': "start",
    }

    buttons = [
        {
            CMD_WHO_NOW: "get_conn_devices",
            CMD_LAST1H: "get_last1h_devices",
            CMD_HISTORY: "get_recent_devices_activity",
        },
        {
            CMD_ADD_PERSON: "add_person",
            CMD_ADD_DEVICE: "add_device",
        }
    ]

    def start(self, _):
        self.chat.reply("It works", new_state=BotMainState)

    def get_conn_devices(self):
        if scanner.last_scan is None:
            self.chat.reply("Scanner is not started yet")
            return

        all_results = ScanResult\
            .filter(ScanResult.time == scanner.last_scan)\
            .join(Device, JOIN.LEFT_OUTER)
        anon_results = []

        msg_text = "Connected devices as of %s\n" % scanner.last_scan.strftime("%Y.%m.%d %X")

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

    def get_last1h_devices(self):
        if scanner.last_scan is None:
            self.chat.reply("⚠️ Scanner is not started yet")

        now = datetime.now()

        results = ScanResult\
            .select()\
            .where(ScanResult.time > now - timedelta(hours=1))\
            .join(Device, JOIN.LEFT_OUTER)\
            .join(Person, JOIN.LEFT_OUTER)\
            .group_by(ScanResult.mac_addr)\
            .having(fn.Max(ScanResult.time) == ScanResult.time)\
            .order_by(-ScanResult.time, NodeList((Person.name, SQL('IS NULL'))), Person.name)

        msg_text = "Active in the last hour devices list\nAs of %s\n" % now.strftime("%Y.%m.%d %X")

        for k, g in groupby(results, lambda x: x.time):
            age = int((now - k).seconds / 60)
            msg_text += "\n<b>%s min ago</b>\n" % str(age) if age > 0 else "\n<b>Now</b>\n"
            for r in g:
                if r.device:
                    d = r.device
                    msg_text += "• %s (%s) \n" % (
                        d.owner.name if d.owner else "N/A",
                        d.name or "N/A"
                    )
                else:
                    msg_text += "• <code>%s</code>\n" % r.mac_addr

        self.chat.reply(
            msg_text,
            parse_mode='HTML',
        )

    def get_recent_devices_activity(self):
        if scanner.last_scan is None:
            self.chat.reply("⚠️ Scanner is not started yet")

        results = ScanResult\
            .select()\
            .join(Device, JOIN.LEFT_OUTER)\
            .group_by(ScanResult.mac_addr)\
            .having(fn.Max(ScanResult.time) == ScanResult.time)\
            .order_by(-ScanResult.time, -Device.owner)

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

        msg_text = "Recent active devices list\nAs of %s\n" % now.strftime("%Y.%m.%d %X")

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
            "User registration.\n"
            "Please, enter the name.",
            new_state=BotAddPersonState,
        )

    def add_device(self):
        self.chat.reply(
            "Device registration (step 1/3).\n\n"
            "Please, send me the MAC address of the device you're registering.\n"
            "It's recommended to enclose it in grave accents (`) to prevent substitution of the text with emoji.",
            new_state=BotAddDeviceState,
        )

    def default(self, text):
        self.chat.reply(
            "Please, use one of the commands from the keyboard below.",
            new_state=type(self),
        )


class BotAddPersonState(BotState):

    buttons = [{CMD_CANCEL: "cancel"}]

    def default(self, text):
        Person(name=text).save()
        self.chat.reply(
            "Person has been saved",
            new_state=BotMainState,
        )

    def cancel(self):
        self.chat.reply(
            "Person registration canceled",
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
                self.chat.reply("Device registration (step 2/3).\n"
                                "MAC address: %s\n"
                                "\n"
                                "Please, name this device." % self.mac_addr)
            else:
                self.chat.reply("It's not a valid MAC address. A valid MAC address consists of six 8-bit "
                                "hexadecimal numbers joined with colons or hyphens.")
        elif self.name is None:
            self.name = text
            self.chat.inline(
                "Device registration (step 3/3).\n"
                "MAC address: %s\n"
                "Name: %s\n\n"
                "Finally, enter the name of the device owner." % (self.mac_addr, self.name),
                markup=SearchKeyboard,
            )
        else:
            try:
                owner = Person.get(Person.name == text)
                dev = Device(mac_addr=self.mac_addr, name=self.name, owner=owner)
                dev.save()
                ScanResult.update(device=dev).where(ScanResult.mac_addr == self.mac_addr).execute()
                self.chat.reply(
                    "Device has been saved",
                    new_state=BotMainState,
                )
            except Person.DoesNotExist:
                self.chat.reply(
                    "I don't know anybody with such name. Please, try again or use search.",
                    markup=SearchKeyboard,
                )

    def cancel(self):
        self.chat.reply(
            "Device registration canceled",
            new_state=BotMainState,
        )

    def inline_query(self, query):
        data = query['query'].lstrip()
        results = []
        if self.mac_addr is not None and self.name is not None:
            print("\"%s\"" % data)
            users = Person.select().where(Person.name.contains(data))

            for user in users:
                results.append(InlineQueryResultArticle(
                    id=user.name,
                    title=user.name,
                    input_message_content={"message_text": user.name},
                ))

        return results


class NewDeviceAlertKeyboard(InlineKeyboard):
    buttons = [{
        CMD_REGISTER: ("callback", "register"),
    }]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mac_addr = None

    def register(self, query):
        msg_id = query['message']['message_id']

        try:
            device = Device.get(Device.mac_addr == self.mac_addr)
            self.chat.reply(
                "This device is registered already\n"
                "MAC address: %s\n"
                "Name: %s\n"
                "Owner: %s" % (device.mac_addr, device.name, device.owner.name)
            )
            self.chat.edit(msg_id, markup=InlineKeyboard)
            return
        except Device.DoesNotExist:
            pass

        self.chat.reply(
            "Device registration (step 2/3).\n"
            "MAC address: %s\n"
            "\n"
            "Please, name this device." % self.mac_addr,
            new_state=BotAddDeviceState,
            setup={"mac_addr": self.mac_addr},
        )


class SearchKeyboard(InlineKeyboard):
    buttons = [{
        CMD_SEARCH: ("switch_inline_query_current_chat", ""),
    }]


def new_device_alert(mac_addr):
    admin_chat = bot.get_or_create_chat(ADMIN_CHAT)
    admin_chat.inline(
        "New device has been detected!\nMAC address: <code>%s</code>" % mac_addr,
        parse_mode='HTML',
        markup=NewDeviceAlertKeyboard,
        setup={"mac_addr": mac_addr},
    )


if __name__ == "__main__":

    with open(os.path.join(os.path.dirname(__file__), 'lanwatcher.yml')) as f:
        settings = yaml.safe_load(f.read())
        TOKEN = settings["bot_token"]
        ADMIN_CHAT = settings["admin_chat"]
        INTERVAL = settings["scan_interval"]
        SCANNER = settings["scanner"]

    scanner_type = SCANNER['type']
    if scanner_type == "arping":
        scanner = ARPScanner(INTERVAL, SCANNER["interface"], SCANNER["subnet"])
    elif scanner_type == "routeros_api":
        ssl_context = ssl.create_default_context()
        ssl_context.load_verify_locations(SCANNER["cert_file"])
        ssl_context.check_hostname = False

        subnet_filters = SCANNER.get("subnets", None)

        scanner = RouterOsScanner(
            INTERVAL, SCANNER['address'], SCANNER["username"], SCANNER["password"], ssl_context, subnet_filters
        )
    else:
        raise ValueError("Unknown scanner type. Should be one of ['arping', 'routeros_api']")

    scanner.set_new_device_alert(new_device_alert)

    bot = TelegramBot(TOKEN, BotMainState)
    bot.allow_chat(ADMIN_CHAT)
    print("Bot started")

    scanner.start_scan()
    print("Scanner started")

    while True:
        sleep(300)
