import os
import pdfplumber
import re
import telebot
from telebot import types
from collections import defaultdict
from datetime import date

token = 'YOUR_TOKEN'
bot = telebot.TeleBot(token)

pattern = re.compile(
    r'(\d{2}\.\d{2}\.\d{4})\s+(\d{2}\.\d{2}\.\d{4})\s+'
    r'([+-]?\s?\d[\d\s]*\.\d{2}\s?[₽Դ$€¥])\s+'
    r'([+-]?\s?\d[\d\s]*\.\d{2}\s?[₽Դ$€¥])\s+'
    r'(.+?)\s+(\d{4})'
)


@bot.message_handler(commands=['start'])
def start_message(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    action_button = types.KeyboardButton("Получить список текущих подписок")
    markup.add(action_button)
    bot.send_message(message.chat.id, text="Привет, {0.first_name} \nВоспользуйся кнопками".format(message.from_user),
                     reply_markup=markup)


@bot.message_handler(content_types=['text'])
def buttons(message):
    if (message.text == "Получить список текущих подписок"):
        bot.send_message(message.chat.id, text="Отправь мне файл-выписку из банка в pdf формате")
        bot.register_next_step_handler(message, parse_pdf)
    else:
        bot.send_message(message.chat.id, text="Я могу отвечать только на нажатие кнопок")


def parse_pdf(message):
    if not message.document or not message.document.file_name.endswith(".pdf"):
        bot.send_message(message.chat.id, "Пришли PDF-файл")
        return

    file_path = f"tgfile_{message.chat.id}_{message.message_id}.pdf"
    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        with open(file_path, "wb") as f:
            f.write(downloaded_file)

        operations = []

        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                text = re.sub(r'-\s*\n\s*', '-', text)
                text = re.sub(r'\n', ' ', text)
                text = re.sub(r'\s+', ' ', text)

                for m in pattern.finditer(text):
                    date1, date2, sum1, sum2, desc, card = m.groups()
                    desc = re.sub(r'\d{2}:\d{2}', '', desc)
                    desc = re.sub(r'\b\d{4}\b', '', desc)
                    desc = re.sub(r'\s+', ' ', desc).strip()
                    operations.append((date1, sum2.strip(), desc))

        today = date.today()
        if today.month == 1:
            last_month_year = today.year - 1
            last_month = 12
        else:
            last_month_year = today.year
            last_month = today.month - 1

        groups = defaultdict(list)

        for date_str, sum_str, desc in operations:
            if not sum_str.strip().startswith("-"):
                continue

            key = desc.strip() + " | " + sum_str.strip()

            parts = date_str.split(".")
            if len(parts) != 3:
                continue
            year = int(parts[2])
            month = int(parts[1])

            groups[key].append((year, month))

        active = []

        for key, months_list in groups.items():
            if len(months_list) < 3:
                continue

            months_count = defaultdict(int)
            for y, m in months_list:
                months_count[(y, m)] += 1

            if any(cnt > 1 for cnt in months_count.values()):
                continue

            if (last_month_year, last_month) in months_count:
                active.append((key, len(months_list)))

        lines = []

        if active:
            lines.append("Активные подписки:")
            for key, count in active:
                lines.append(f"{key}")
        else:
            lines.append("Активных подписок нет")

        preview = "\n".join(lines)
        bot.send_message(message.chat.id, preview)

    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка при обработке файла: {e}")

    finally:
        if os.path.exists(file_path):
            os.remove(file_path)


bot.polling(none_stop=True, interval=0)