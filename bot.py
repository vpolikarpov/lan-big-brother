import re
import telepot
from telepot.loop import MessageLoop
from telepot.namedtuple import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton


def build_keyboard(buttons, inline=False):
    button_cls = InlineKeyboardButton if inline else KeyboardButton
    keyboard = []
    for row in buttons:
        kb_row = []
        for label in row:
            ar = row[label].copy() if isinstance(row[label], dict) else {"callback": row[label]}
            ar["text"] = label
            if "callback" in ar:
                ar["callback_data"] = label
                ar.pop("callback")
            kb_row.append(button_cls(
                **ar,
            ))
        keyboard.append(kb_row)

    if inline:
        return InlineKeyboardMarkup(
            inline_keyboard=keyboard,
        )
    else:
        return ReplyKeyboardMarkup(
            keyboard=keyboard,
            resize_keyboard=True,
        )


class BotState:

    buttons = []
    commands = {}
    patterns = {}

    inline_query_kwargs = {
        "is_personal": True,
    }

    def __init__(self, chat):
        self.chat = chat

        self.buttons_dict = {}
        for row in self.buttons:
            for label in row:
                self.buttons_dict[label] = row[label]

    def default(self, text):
        pass

    def inline_query(self, query):
        pass


class InlineKeyboard:

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
        action_setup = keyboard.buttons_dict.get(data)

        if isinstance(action_setup, dict):
            action_name = action_setup["callback"]
        else:
            action_name = action_setup

        action = getattr(keyboard, action_name)
        action(query)

    def inline_query(self, query):
        results = self.state.inline_query(query)
        self.bot.answerInlineQuery(query['id'], results, **self.state.inline_query_kwargs)

    def reply(self, text, new_state=None, setup=None, parse_mode=None, disable_web_page_preview=None,
              disable_notification=None, reply_to_message_id=None, reply_markup=None):

        if new_state is not None and new_state.buttons is not None:
            if reply_markup is not None:
                raise Exception("Reply markup is already set. Unable to change state.")

            reply_markup = build_keyboard(new_state.buttons)

        self.bot.sendMessage(self.chat_id, text, parse_mode, disable_web_page_preview,
                             disable_notification, reply_to_message_id, reply_markup)

        if new_state is not None:
            self.state = s = new_state(self)
            if setup is not None:
                for field in setup:
                    setattr(s, field, setup[field])

    def inline(self, text, markup=None, setup=None, parse_mode=None, disable_web_page_preview=None,
               disable_notification=None, reply_to_message_id=None, reply_markup=None):

        if markup is not None and markup.buttons is not None:
            if reply_markup is not None:
                raise Exception("Reply markup is already set. Unable to init inline keyboard.")
            reply_markup = build_keyboard(markup.buttons, inline=True)

        reply = self.bot.sendMessage(self.chat_id, text, parse_mode, disable_web_page_preview,
                                     disable_notification, reply_to_message_id, reply_markup)

        if markup is not None and markup.buttons is not None:
            self.keyboards[reply['message_id']] = m = markup(self)
            if setup is not None:
                for field in setup:
                    setattr(m, field, setup[field])

    def edit(self, message_id, text=None, markup=None, setup=None, parse_mode=None,
             disable_web_page_preview=None, reply_markup=None):
        msg_pointer = (self.chat_id, message_id)

        if markup is None and reply_markup is None:
            markup = self.keyboards.get(message_id, None)

        if markup is not None and markup.buttons is not None:
            if reply_markup is not None:
                raise Exception("Reply markup is already set. Unable to init inline keyboard.")
            reply_markup = build_keyboard(markup.buttons, inline=True)

        if text is not None:
            self.bot.editMessageText(msg_pointer, text, parse_mode, disable_web_page_preview, reply_markup)
        else:
            self.bot.editMessageReplyMarkup(msg_pointer, reply_markup)

        if markup is not None and markup.buttons is not None:
            self.keyboards[message_id] = m = markup(self)
            if setup is not None:
                for field in setup:
                    setattr(m, field, setup[field])


class TelegramBot:
    def __init__(self, token, initial_state):
        self.allowed_chats = []

        self.bot = telepot.Bot(token)
        MessageLoop(self.bot, {
            'chat': self.on_chat_message,
            'callback_query': self.on_callback_query,
            'inline_query': self.on_inline_query,
            'chosen_inline_result': self.on_chosen_inline_result,
        }).run_as_thread()

        self.initial_state = initial_state
        self.chats = {}

    def allow_chat(self, chat_id):
        self.allowed_chats.append(chat_id)

    def get_or_create_chat(self, chat_id):
        if chat_id not in self.chats:
            self.chats[chat_id] = chat = ChatFSM(self.bot, chat_id)
            chat.set_state(self.initial_state)
            return chat
        else:
            return self.chats[chat_id]

    def on_chat_message(self, msg):
        content_type, chat_type, chat_id = telepot.glance(msg)

        if chat_id not in self.allowed_chats:
            self.bot.sendMessage(chat_id, "Ошибка доступа")
            return

        chat = self.get_or_create_chat(chat_id)
        chat.message(msg)

    def on_callback_query(self, query):
        chat_id = query['message']['chat']['id']

        if chat_id not in self.allowed_chats:
            return

        chat = self.get_or_create_chat(chat_id)
        chat.query(query)

    def on_inline_query(self, query):
        chat_id = query['from']['id']

        if chat_id not in self.allowed_chats:
            return

        chat = self.get_or_create_chat(chat_id)
        chat.inline_query(query)

    def on_chosen_inline_result(self, query):
        print(">> " + query['query'])
