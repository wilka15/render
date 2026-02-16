import os
import base64
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

from openai import OpenAI

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

client = OpenAI(
    api_key=OPENAI_API_KEY,
    base_url="https://routerai.ru/api/v1"
)

user_memory = {}
MAX_HISTORY = 10

def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🧹 Очистить память", callback_data="clear"),
         InlineKeyboardButton("ℹ️ О боте", callback_data="about")]
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я SmartAI-бот 🤖\n"
        "Я могу отвечать на твои вопросы и решать задания по фото.",
        reply_markup=main_keyboard()
    )

async def commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "/start - старт бота\n"
        "/commands - список команд\n"
        "/info - информация о боте\n"
        "Просто отправь текст или фото с заданием."
    )

async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Я GPT-бот с памятью и поддержкой RouterAI.\n"
        "Модель: openai/gpt-4o"
    )

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id

    if query.data == "clear":
        user_memory[uid] = []
        await query.edit_message_text("🧹 Память очищена!")
    elif query.data == "about":
        await query.edit_message_text("GPT-бот через RouterAI 🤖")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    text = update.message.text

    history = user_memory.get(uid, [])
    history.append({"role": "user", "content": text})
    history = history[-MAX_HISTORY:]

    try:
        response = client.chat.completions.create(
            model="openai/gpt-4o",
            messages=[
                {"role": "system", "content": "Ты полезный и дружелюбный ассистент."},
                *history
            ],
            max_tokens=700
        )

        answer = response.choices[0].message.content
        history.append({"role": "assistant", "content": answer})
        user_memory[uid] = history

        await update.message.reply_text(answer, reply_markup=main_keyboard())

    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")

async def handle_homework_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    file = await photo.get_file()
    img_bytes = await file.download_as_bytearray()
    b64_image = base64.b64encode(img_bytes).decode()

    try:
        response = client.chat.completions.create(
            model="openai/gpt-4o",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Реши задание на фото и объясни пошагово."},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{b64_image}"
                        }
                    }
                ]
            }],
            max_tokens=1000
        )

        answer = response.choices[0].message.content
        await update.message.reply_text(f"📘 Решение:\n\n{answer}")

    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("commands", commands))
    app.add_handler(CommandHandler("info", info))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_homework_image))

    print("🤖 Бот запущен")
    app.run_polling()

if __name__ == "__main__":
    main()

