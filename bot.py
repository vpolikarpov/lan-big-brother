import re
import threading
import telebot


def build_keyboard(buttons, inline=False):
    markup = telebot.types.InlineKeyboardMarkup() if inline else telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)

    button_cls = telebot.types.InlineKeyboardButton if inline else telebot.types.KeyboardButton
    for row in buttons:
        kb_row = []
        for label in row:
            ar = {"text": label}

            btn = row[label]
            if isinstance(btn, tuple):
                if btn[0] == "callback":
                    ar["callback_data"] = label
                else:
                    ar[btn[0]] = btn[1]

            kb_row.append(button_cls(**ar))
        markup.row(*kb_row)

    return markup


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
        state = self.state

        if msg.content_type == 'text':
            text = msg.text
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

    def callback_query(self, query):
        data = query.data
        keyboard = self.keyboards[query.message.message_id]
        action_setup = keyboard.buttons_dict.get(data)

        if isinstance(action_setup, tuple) and action_setup[0] == "callback":
            action_name = action_setup[1]
        else:
            action_name = str(action_setup)

        action = getattr(keyboard, action_name)
        action(query)

    def inline_query(self, query):
        results = self.state.inline_query(query)
        self.bot.answer_inline_query(query.id, results,
                                     **self.state.inline_query_kwargs)

    def reply(self, text, new_state=None, setup=None, parse_mode=None, disable_web_page_preview=None,
              disable_notification=None, reply_to_message_id=None, reply_markup=None):

        if new_state is not None and new_state.buttons is not None:
            if reply_markup is not None:
                raise Exception("Reply markup is already set. Unable to change state.")

            reply_markup = build_keyboard(new_state.buttons)

        self.bot.send_message(self.chat_id, text,
                              parse_mode=parse_mode,
                              disable_web_page_preview=disable_web_page_preview,
                              disable_notification=disable_notification,
                              reply_to_message_id=reply_to_message_id,
                              reply_markup=reply_markup)

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

        reply = self.bot.send_message(self.chat_id, text,
                                      parse_mode=parse_mode,
                                      disable_web_page_preview=disable_web_page_preview,
                                      disable_notification=disable_notification,
                                      reply_to_message_id=reply_to_message_id,
                                      reply_markup=reply_markup)

        if markup is not None and markup.buttons is not None:
            self.keyboards[reply.message_id] = m = markup(self)
            if setup is not None:
                for field in setup:
                    setattr(m, field, setup[field])

    def edit(self, message_id, text=None, markup=None, setup=None, parse_mode=None,
             disable_web_page_preview=None, reply_markup=None):

        if markup is None and reply_markup is None:
            markup = self.keyboards.get(message_id, None)

        if markup is not None and markup.buttons is not None:
            if reply_markup is not None:
                raise Exception("Reply markup is already set. Unable to init inline keyboard.")
            reply_markup = build_keyboard(markup.buttons, inline=True)

        if text is not None:
            self.bot.edit_message_text(text,
                                       chat_id=self.chat_id,
                                       message_id=message_id,
                                       parse_mode=parse_mode,
                                       disable_web_page_preview=disable_web_page_preview,
                                       reply_markup=reply_markup)
        else:
            self.bot.edit_message_reply_markup(chat_id=self.chat_id,
                                               message_id=message_id,
                                               reply_markup=reply_markup)

        if markup is not None and markup.buttons is not None:
            self.keyboards[message_id] = m = markup(self)
            if setup is not None:
                for field in setup:
                    setattr(m, field, setup[field])


class TelegramBot:
    def __init__(self, token, initial_state):
        self.allowed_chats = []

        self.bot = telebot.TeleBot(token=token)
        self.bot.register_message_handler(self.on_chat_message, content_types=['text'])
        self.bot.register_callback_query_handler(self.on_callback_query, lambda _: True)
        self.bot.register_inline_handler(self.on_inline_query, lambda _: True)
        self.bot.register_chosen_inline_handler(self.on_chosen_inline_result, lambda _: True)

        self.initial_state = initial_state
        self.chats = {}

        self.polling_thread = threading.Thread(target=self.bot.infinity_polling)

    def start(self):
        self.polling_thread.start()

    def stop(self):
        self.bot.stop_bot()
        self.polling_thread.join()

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
        chat_id = msg.chat.id

        if chat_id not in self.allowed_chats:
            self.bot.send_message(chat_id, "Ошибка доступа")
            print("Access denied for chat#{}".format(chat_id))
            return

        chat = self.get_or_create_chat(chat_id)
        chat.message(msg)

    def on_callback_query(self, query):
        chat_id = query.message.chat.id

        if chat_id not in self.allowed_chats:
            return

        chat = self.get_or_create_chat(chat_id)
        chat.callback_query(query)

    def on_inline_query(self, query):
        chat_id = query.from_user.id

        if chat_id not in self.allowed_chats:
            return

        chat = self.get_or_create_chat(chat_id)
        chat.inline_query(query)

    def on_chosen_inline_result(self, query):
        print(">> " + query.query)
