import re
import telepot
from telepot.loop import MessageLoop
from telepot.namedtuple import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton


class BotState:

    buttons = []
    commands = {}
    patterns = {}

    def __init__(self, chat):
        self.chat = chat

        self.buttons_dict = {}
        for row in self.buttons:
            for label in row:
                self.buttons_dict[label] = row[label]

    def default(self, text):
        pass


class KeyboardMarkup:

    buttons = []

    def __init__(self, chat):
        self.chat = chat

        self.buttons_dict = {}
        for row in self.buttons:
            for label in row:
                self.buttons_dict[label] = row[label]


class ChatFSM:
    def __init__(self, bot, chat_id):
        self.bot = bot
        self.chat_id = chat_id
        self.state = None
        self.storage = {}
        self.keyboards = {}

    def set_state(self, state):
        self.state = state(self)

    def message(self, msg):
        content_type, chat_type, chat_id = telepot.glance(msg)

        state = self.state

        if content_type == 'text':
            text = msg['text']
            cmd_args = text.split(" ")
            cmd_name = cmd_args.pop(0)

            matched = False

            if cmd_name in state.commands:
                matched = True
                action_name = state.commands.get(cmd_name)
                action = getattr(state, action_name)
                action(cmd_args)
            elif text in state.buttons_dict:
                matched = True
                action_name = state.buttons_dict.get(text)
                action = getattr(state, action_name)
                action()
            else:
                for pattern in state.patterns:
                    match = re.search(pattern, text)
                    if not match:
                        continue
                    matched = True

                    action_name = state.patterns.get(pattern)
                    action = getattr(state, action_name)
                    action(text)

            if not matched:
                state.default(text)

    def query(self, query):
        data = query['data']
        keyboard = self.keyboards[query['message']['message_id']]
        action_name = keyboard.buttons_dict.get(data)
        action = getattr(keyboard, action_name)
        action()

    def reply(self, text, new_state=None, parse_mode=None, disable_web_page_preview=None,
              disable_notification=None, reply_to_message_id=None, reply_markup=None):

        if new_state is not None and new_state.buttons is not None:
            if reply_markup is not None:
                raise Exception("Reply markup is already set. Unable to change state.")

            keyboard = []
            for row in new_state.buttons:
                kb_row = []
                for label in row:
                    kb_row.append(KeyboardButton(text=label))
                keyboard.append(kb_row)

            reply_markup = ReplyKeyboardMarkup(
                keyboard=keyboard,
                resize_keyboard=True,
            )

        self.bot.sendMessage(self.chat_id, text, parse_mode, disable_web_page_preview,
                             disable_notification, reply_to_message_id, reply_markup)

        if new_state is not None:
            self.state = new_state(self)

    def inline(self, text, markup=None, parse_mode=None, disable_web_page_preview=None,
               disable_notification=None, reply_to_message_id=None, reply_markup=None):

        if markup is not None and markup.buttons is not None:
            if reply_markup is not None:
                raise Exception("Reply markup is already set. Unable to change state.")

            keyboard = []
            for row in markup.buttons:
                kb_row = []
                for label in row:
                    kb_row.append(InlineKeyboardButton(
                        text=label,
                        callback_data=label,
                    ))
                keyboard.append(kb_row)

            reply_markup = InlineKeyboardMarkup(
                inline_keyboard=keyboard,
            )

        reply = self.bot.sendMessage(self.chat_id, text, parse_mode, disable_web_page_preview,
                                     disable_notification, reply_to_message_id, reply_markup)

        if markup is not None and markup.buttons is not None:
            self.keyboards[reply['message_id']] = markup


class TelegramBot:
    def __init__(self, token, initial_state):
        self.allowed_chats = []

        self.bot = telepot.Bot(token)
        MessageLoop(self.bot, {'chat': self.on_chat_message, 'callback_query': self.on_callback_query}).run_as_thread()

        self.initial_state = initial_state
        self.chats = {}

    def allow_chat(self, chat_id):
        self.allowed_chats.append(chat_id)

    def on_chat_message(self, msg):
        content_type, chat_type, chat_id = telepot.glance(msg)

        if chat_id not in self.allowed_chats:
            self.bot.sendMessage(chat_id, "Ошибка доступа")
            return

        if chat_id not in self.chats:
            self.chats[chat_id] = chat = ChatFSM(self.bot, chat_id)
            chat.set_state(self.initial_state)

        chat = self.chats[chat_id]
        chat.message(msg)

    def on_callback_query(self, query):
        chat_id = query['message']['chat']['id']

        if chat_id not in self.allowed_chats:
            self.bot.sendMessage(chat_id, "Ошибка доступа")
            return

        if chat_id not in self.chats:
            return

        chat = self.chats[chat_id]
        chat.query(query)

    def alert_all(self, text, new_state=None, parse_mode=None, disable_web_page_preview=None,
                  disable_notification=None, reply_to_message_id=None, reply_markup=None):
        for chat_id in self.chats:
            self.chats[chat_id].reply(text, new_state, parse_mode, disable_web_page_preview,
                                      disable_notification, reply_to_message_id, reply_markup)

    def inline_all(self, text, markup=None, parse_mode=None, disable_web_page_preview=None,
                   disable_notification=None, reply_to_message_id=None, reply_markup=None):
        for chat_id in self.chats:
            self.chats[chat_id].inline(text, markup, parse_mode, disable_web_page_preview,
                                       disable_notification, reply_to_message_id, reply_markup)
