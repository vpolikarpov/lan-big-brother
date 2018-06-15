#!/usr/bin/python3

import os
import yaml
from datetime import datetime

from telepot.namedtuple import ReplyKeyboardMarkup, KeyboardButton

from bot import TelegramBot, BotState
from models import Device, ScanResult, JOIN_LEFT_OUTER, fn
from scanner import lan_scanner


def format_datetime(dt):
    now = datetime.now()
    interval = now - dt
    if interval.days < 180:
        return dt.strftime("%d %b, %H:%M")
    else:
        return dt.strftime("%d %b %Y")


class BotMainState(BotState):
    def __init__(self, tg_bot, chat_id):
        super().__init__(tg_bot, chat_id)

        self.patterns = {
            '/start': "start",
            'Кто сейчас': "get_conn_devices",
            'Кто когда': "get_last_devices",
        }

    def start(self, _):
        self.bot.sendMessage(self.chat_id, "Работаем",
                             reply_markup=ReplyKeyboardMarkup(keyboard=[
                                 [
                                     KeyboardButton(text="Кто сейчас"),
                                     KeyboardButton(text="Кто когда"),
                                 ]
                             ], resize_keyboard=True)
                             )

    def get_conn_devices(self, _):
        all_results = ScanResult.filter(ScanResult.time == lan_scanner.last_scan).join(Device, JOIN_LEFT_OUTER)
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

        self.bot.sendMessage(self.chat_id, msg_text, parse_mode='HTML')

    def get_last_devices(self, _):
        all_results = ScanResult\
            .select()\
            .join(Device, JOIN_LEFT_OUTER)\
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

        self.bot.sendMessage(self.chat_id, msg_text, parse_mode='HTML')


if __name__ == "__main__":

    with open(os.path.join(os.path.dirname(__file__), 'lanwatcher.yml')) as f:
        settings = yaml.load(f.read())
        TOKEN = settings["bot_token"]
        ADMIN_CHAT = settings["admin_chat"]
        INTERVAL = settings["scan_interval"]
        INTERFACE = settings["interface"]
        SUBNET = settings["subnet"]

    lan_scanner.start_scan(INTERVAL, INTERFACE, SUBNET)
    print("Scan started")

    bot = TelegramBot(TOKEN, BotMainState)
    bot.allow_chat(ADMIN_CHAT)
    print("Bot started")
