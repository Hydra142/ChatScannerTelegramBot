import datetime
import re

import telebot
from telebot import types
import sqlite3
import os
import tempfile
# Отримання токену бота та пароля з змінних середовища
TOKEN = os.environ.get('BOT_TOKEN')
PASSWORD = os.environ.get('PASSWORD')
# Ініціалізація бота
bot = telebot.TeleBot(TOKEN)

# Клас для роботи з базою даних
class DbConnector:
    # Ініціалізація конектора бази даних
    def __init__(self, db_name):
        self.db_name = db_name
        self.create_tables()

    # Створення таблиць у базі даних, якщо вони не існують
    def create_tables(self):
        conn = sqlite3.connect(self.db_name)
        cur = conn.cursor()
        # таблиця для збереження налаштувать чатів
        cur.execute('''CREATE TABLE IF NOT EXISTS chats
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER UNIQUE,
                    name TEXT,
                    is_monitoring_enabled BOOLEAN)''')
        # таблиця для зберігання списку заоронених слів
        cur.execute('''CREATE TABLE IF NOT EXISTS messages_black_list
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message TEXT UNIQUE)''')
        # таблиця для збереження повідомлень які містять заборонені свлова
        cur.execute('''CREATE TABLE IF NOT EXISTS messages_history
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_name TEXT,
                    user_name TEXT,
                    message_text TEXT,
                    sent_datetime TEXT,
                    matched_forbidden_words TEXT)''')

        conn.commit()
        conn.close()

    # Метод для читання даних з бази даних
    def read(self, query, params=()):
        conn = sqlite3.connect(self.db_name)
        cur = conn.cursor()
        cur.execute(query, params)
        result = cur.fetchall()
        conn.close()
        return result

    # Метод для запису даних у базу даних
    def write(self, query, params=()):
        conn = sqlite3.connect(self.db_name)
        cur = conn.cursor()
        cur.execute(query, params)
        conn.commit()
        conn.close()


# Ініціалізація об'єкта для роботи з базою даних
db = DbConnector("scanner_bot.db")
# Визначення дії за замовчуванням при виявленні забороненого слова
forbidden_message_action = "Delete"


def check_password(message):
    return message.text == PASSWORD


# Функція для перевірки, чи є чат приватним
def is_private_chat(chat):
    return chat.type == 'private'


# перевірка введеного паролю
def handle_password(message):
    if check_password(message):
        bot.send_message(message.chat.id, "Access granted. You can now manage the bot.",
                         reply_markup=get_user_menu_markup())
    else:
        bot.send_message(message.chat.id, "Access denied. Invalid password.")


# виведення списку чатів
def handle_show_chats(message):
    chat_list = db.read("SELECT chat_id, name, is_monitoring_enabled FROM chats")
    if chat_list:
        formatted_list = '\n'.join(
            [f"Chat ID: {chat[0]}, Name: {chat[1]}, Monitoring: {'Enabled' if chat[2] else 'Disabled'}" for chat in
             chat_list])
        bot.send_message(message.chat.id, f"Chats:\n{formatted_list}")
    else:
        bot.send_message(message.chat.id, "No chats found.")


# видалення слова з чорного списку
def handle_delete_blacklist_word(message):
    word_to_delete = message.text
    db.write("DELETE FROM messages_black_list WHERE message=?", (word_to_delete,))
    bot.send_message(message.chat.id, f"Deleted word '{word_to_delete}' from the blacklist.",
                     reply_markup=get_user_menu_markup())


# видалення історії заборонених повідомлень
def handle_delete_messages_history(message):
    db.write("DELETE FROM messages_history")
    bot.send_message(message.chat.id, "Deleted all messages history.")


# додавання слова до списку забаронених слів
def handle_add_blacklist_word(message):
    word = message.text
    try:
        db.write("INSERT INTO messages_black_list (message) VALUES (?)", (word,))
        bot.reply_to(message, f"Added '{word}' to the blacklist.", reply_markup=get_user_menu_markup())
    except sqlite3.IntegrityError:
        bot.reply_to(message, f"'{word}' is already in the blacklist.", reply_markup=get_user_menu_markup())


# виведення до списку забаронених слів
def handle_show_blacklist(message):
    blacklist = db.read("SELECT message FROM messages_black_list")
    if blacklist:
        formatted_list = '\n'.join([word[0] for word in blacklist])
        bot.send_message(message.chat.id, f"Blacklist:\n{formatted_list}")
    else:
        bot.send_message(message.chat.id, "The blacklist is empty.")


# запуск моніторингу в визначеному чаті
def handle_enable_monitoring(message):
    chat_id = message.text
    db.write("UPDATE chats SET is_monitoring_enabled = 1 WHERE chat_id = ?", (chat_id,))
    bot.reply_to(message, f"Monitoring enabled for chat ID {chat_id}.")


# зупинка моніторингу в визначеному чаті
def handle_disable_monitoring(message):
    chat_id = message.text
    db.write("UPDATE chats SET is_monitoring_enabled = 0 WHERE chat_id = ?", (chat_id,))
    bot.reply_to(message, f"Monitoring disabled for chat ID {chat_id}.")


# видалення спец символів з тексту
def remove_special_chars_and_spaces(text):
    pattern = r'[^\w\s\d]'
    text_without_special_chars = re.sub(pattern, '', text)
    return text_without_special_chars


# перевірка чи містить текст заборонені слова
def check_forbidden_words(message_text):
    # отримання списку заборонених слів
    black_list = db.read("SELECT message FROM messages_black_list")
    # видалення спеціальних символів
    message_text = remove_special_chars_and_spaces(message_text)
    # перебір і вибірка заборонених слів в повідомленні
    forbidden_words = [word[0].lower() for word
                       in black_list if word[0].lower()
                       in message_text.lower().split()
                       ]
    # видалення дублікатів
    forbidden_words = list(set(forbidden_words))
    return forbidden_words


# запис інформації про повідомлення яке містить заборонені слова
def add_to_messages_history(chat_name, user_name, message_text, sent_datetime, matched_forbidden_words):
    db.write('''INSERT INTO messages_history
                (chat_name, user_name, message_text, sent_datetime, matched_forbidden_words)
                VALUES (?, ?, ?, ?, ?)''', (chat_name, user_name, message_text, sent_datetime, matched_forbidden_words))


# початкова точка входу до бота
@bot.message_handler(commands=['start'])
def handle_start(message):
    chat = message.chat
    if is_private_chat(chat):
        bot.send_message(chat.id, "Enter password to continue:")
        bot.register_next_step_handler(message, handle_password)


# виведення меню
def get_user_menu_markup():
    global forbidden_message_action
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    markup.add(
        types.KeyboardButton("Show blacklist"),
        types.KeyboardButton("Add to blacklist"),
        types.KeyboardButton("Delete blacklist word")
    )
    markup.add(
        types.KeyboardButton("Show chats"),
        types.KeyboardButton("Enable monitoring"),
        types.KeyboardButton("Disable monitoring")
    )
    markup.add(
        types.KeyboardButton("Show messages history"),
        types.KeyboardButton("Delete all messages history"),
        types.KeyboardButton(f"Action:{forbidden_message_action}")
    )

    return markup


# виведення клавіш для довавання/видалення чату до/з списку моніторинга
def get_chat_list_markup(chat_list, prefix):
    markup = types.InlineKeyboardMarkup()
    for chat in chat_list:
        markup.add(types.InlineKeyboardButton(chat[1], callback_data=f"{prefix}:{chat[0]}"))
    return markup


# хендлер який ловить натискання на клавішу виведені в get_chat_list_markup
@bot.callback_query_handler(func=lambda call: call.data.startswith('enable') or call.data.startswith('disable'))
def handle_callback_query(call):
    action, chat_id = call.data.split(':')
    chat_id = int(chat_id)
    # відповідно до дії змінюємо значення is_monitoring_enabled обраного чату
    if action == 'enable':
        db.write("UPDATE chats SET is_monitoring_enabled=1 WHERE chat_id=?", (chat_id,))
        bot.answer_callback_query(call.id, f"Monitoring enabled for chat {chat_id}.")
    elif action == 'disable':
        db.write("UPDATE chats SET is_monitoring_enabled=0 WHERE chat_id=?", (chat_id,))
        bot.answer_callback_query(call.id, f"Monitoring disabled for chat {chat_id}.")

# обробка натиснення на клавішу активації моніторингу
def handle_enable_monitoring(message):
    chat_list = db.read("SELECT chat_id, name FROM chats WHERE is_monitoring_enabled=0")
    if chat_list:
        markup = get_chat_list_markup(chat_list, 'enable')
        bot.send_message(message.chat.id, "Select a chat to enable monitoring:", reply_markup=markup)
    else:
        bot.send_message(message.chat.id, "No chats with disabled monitoring were found.")


# обробка натиснення на клавішу активації моніторингу
def handle_disable_monitoring(message):
    chat_list = db.read("SELECT chat_id, name FROM chats WHERE is_monitoring_enabled=1")
    if chat_list:
        markup = get_chat_list_markup(chat_list, 'disable')
        bot.send_message(message.chat.id, "Select a chat to disable monitoring:", reply_markup=markup)
    else:
        bot.send_message(message.chat.id, "No chats with enabled monitoring were found.")

# показ історії повідомлень з забороненим вмістом
def handle_show_messages_history(message):
    # читання списку з БД
    messages_history = db.read("SELECT * FROM messages_history")
    if messages_history:

        chat_history_text = ""
        # наповнення відповіді в зручному для читання форматі
        for count, history in enumerate(messages_history, start=1):
            chat_history_text += (f"{count}) Chat Name: {history[1]}\n"
                                  f"   User: @{history[2]}\n"
                                  f"   Message: {history[3]}\n"
                                  f"   Sent: {history[4]}\n"
                                  f"   Forbidden Words: {history[5]}\n\n")
        try:
            bot.send_message(message.chat.id, chat_history_text)
        except:
            # через обмеження є можливість того що повідомлення буде завелике
            bot.send_message(message.chat.id, "History is too long!")

        # запис результату в текстовий документ
        with tempfile.NamedTemporaryFile(mode="w+", delete=False) as temp_file:
            temp_file.write(chat_history_text)
            temp_file.flush()
            temp_file.close()
            # надсилання тектсовго документу користувачу
            with open(temp_file.name, "rb") as file:
                bot.send_document(message.chat.id, file, caption="here's your history")
        # видалення файлу
        os.unlink(temp_file.name)
    else:
        # повідомлення в разі відсутності повідомлень
        bot.send_message(message.chat.id, "No messages history found.")


@bot.message_handler(
    func=lambda m: m.text in ["Add to blacklist", "Delete blacklist word",
                              "Show blacklist", "Show chats",
                              "Show messages history", "Delete all messages history",
                              "Enable monitoring", "Disable monitoring",
                              "Action:Delete", "Action:Warning"] and is_private_chat(m.chat))
def handle_menu_options(message):
    chat_id = message.chat.id
    if message.text == "Add to blacklist":
        # додавання слова до чорного списку
        bot.send_message(chat_id, "Enter the word you want to add to the blacklist:")
        bot.register_next_step_handler(message, handle_add_blacklist_word)
    elif message.text == "Delete blacklist word":
        # видалення слова з списку заборонених
        bot.send_message(chat_id, "Enter the word you want to delete from the blacklist:")
        bot.register_next_step_handler(message, handle_delete_blacklist_word)
    elif message.text == "Show blacklist":
        # виведення списку заборонених слів
        handle_show_blacklist(message)
    elif message.text == "Show chats":
        # виведення списку частів
        handle_show_chats(message)
    elif message.text == "Show messages history":
        # виведення історії повідомлень з забороненими словами
        handle_show_messages_history(message)
    elif message.text == "Delete all messages history":
        # видалення історії повідомлень
        handle_delete_messages_history(message)
    elif message.text == "Enable monitoring":
        # запуск поніторигу в чаті
        chat_list = db.read("SELECT chat_id, name FROM chats WHERE is_monitoring_enabled=0")
        if chat_list:
            markup = get_chat_list_markup(chat_list, 'enable')
            bot.send_message(chat_id, "Select a chat to enable monitoring:", reply_markup=markup)
        else:
            bot.send_message(chat_id, "No chats with disabled monitoring were found.")
    elif message.text == "Disable monitoring":
        # зупинка моніторингу в чаті
        chat_list = db.read("SELECT chat_id, name FROM chats WHERE is_monitoring_enabled=1")
        if chat_list:
            markup = get_chat_list_markup(chat_list, 'disable')
            bot.send_message(chat_id, "Select a chat to disable monitoring:", reply_markup=markup)
        else:
            bot.send_message(chat_id, "No chats with enabled monitoring were found.")
    elif message.text in ("Action:Delete", "Action:Warning"):
        # вставновлення типу дії при виявленні забороненого слова
        global forbidden_message_action
        forbidden_message_action = "Delete" if message.text.split(':')[1] == "Warning" else "Warning"
        bot.reply_to(message, f"Changed forbidden word usage action to {forbidden_message_action}",
                     reply_markup=get_user_menu_markup())


@bot.message_handler(func=lambda m: True)
def handle_messages(message):
    chat_id = message.chat.id
    chat_name = message.chat.title

    if not is_private_chat(message.chat):
        # Додати чат в список збережених чатів якщо відсутній
        chat_exists = db.read("SELECT chat_id FROM chats WHERE chat_id = ?", (chat_id,))
        if not chat_exists:
            db.write(
                "INSERT INTO chats (chat_id, name, is_monitoring_enabled) VALUES (?, ?, ?)"
                ,(chat_id, chat_name, 0))

        # Перевірка чи активований моніторинг в даному чаті
        is_monitoring_enabled = db.read(
            "SELECT is_monitoring_enabled FROM chats WHERE chat_id = ?"
            , (chat_id,)
        )[0][0]

        if is_monitoring_enabled:
            # перевірка повідомлення на вміст заборонених слів
            forbidden_words = check_forbidden_words(message.text)

            if forbidden_words:
                # встановлення імені користувача
                user_name = message.from_user.username
                # втсавновлення тексу повідомлення
                message_text = message.text
                # вставнолення часу порушення
                sent_datetime = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                # вставовлення списку забороених слів які були виявдені
                matched_forbidden_words = ', '.join(forbidden_words)
                # збереження запису до БД
                add_to_messages_history(
                    chat_name,
                    user_name,
                    message_text,
                    sent_datetime,
                    matched_forbidden_words
                )
                global forbidden_message_action
                # вибір реакці на порушення
                if forbidden_message_action == "Delete":
                    bot.delete_message(chat_id, message.message_id)
                    bot.send_message(
                        chat_id,
                        f"@{user_name} sent a message"
                        f"containing forbidden words: {matched_forbidden_words}"
                    )
                else:
                    bot.reply_to(
                        message,
                        f"You've sent forbidden words: {matched_forbidden_words}"
                    )


bot.polling(none_stop=True)
