import telepot


class BotState:
    def on_chat_message(self, msg):
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


class TelegramBot:
    def __init__(self, token):
        self.bot = bot
        self.allowed_chats = []

    def allow_chat(self, chat_id):
        self.allowed_chats.append(chat_id)

    def on_chat_message(self, msg):
        content_type, chat_type, chat_id = telepot.glance(msg)

        if chat_id not in self.allowed_chats:
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