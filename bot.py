import re
import telepot
from telepot.loop import MessageLoop


class BotState:
    def __init__(self, tg_bot, chat_id):
        self.bot = tg_bot
        self.chat_id = chat_id


class TelegramBot:
    def __init__(self, token, initial_state):
        self.allowed_chats = []

        self.bot = telepot.Bot(token)
        MessageLoop(self.bot, {'chat': self.on_chat_message}).run_as_thread()

        self.initial_state = initial_state
        self.states = {}

    def allow_chat(self, chat_id):
        self.allowed_chats.append(chat_id)

    def on_chat_message(self, msg):
        content_type, chat_type, chat_id = telepot.glance(msg)

        if chat_id not in self.allowed_chats:
            self.bot.sendMessage(chat_id, "Ошибка доступа")
            return

        if chat_id not in self.states:
            self.states[chat_id] = self.initial_state(self.bot, chat_id)

        state = self.states[chat_id]

        if content_type == 'text':
            text = msg['text']

            matched = False

            for pattern in state.patterns:
                match = re.search(pattern, text)
                if not match:
                    continue

                matched = True
                action_name = state.patterns.get(pattern)
                action = getattr(state, action_name)

                new_state = action(text)

                if new_state:
                    self.states[chat_id] = new_state(self.bot, chat_id)

            if not matched:
                print("Command not found: \"%s\"" % text)
