import os
import base64
import threading
from io import BytesIO
from PIL import Image
from dotenv import load_dotenv

from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

from openai import OpenAI

# ====== Загрузка ключей ======
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

client = OpenAI(api_key=OPENAI_API_KEY)

# ====== Flask server (для деплоя) ======
flask_app = Flask(__name__)

@flask_app.route("/")
def home():
    return "✅ Bot is running"

def run_flask():
    port = int(os.environ.get("PORT", 3000))
    flask_app.run(host="0.0.0.0", port=port)

# ====== Память ======
user_memory = {}
MAX_HISTORY = 10

# ====== Кнопки ======
def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🧹 Очистить память", callback_data="clear"),
         InlineKeyboardButton("ℹ️ О боте", callback_data="about")],
        [InlineKeyboardButton("🎨 Сгенерировать картинку", callback_data="gen_image")]
    ])

# ====== /start ======
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я SmartAI-бот! 🎨",
        reply_markup=main_keyboard()
    )

# ====== Кнопки ======
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == "clear":
        user_memory[user_id] = []
        await query.edit_message_text("🧹 Память очищена!")

    elif query.data == "about":
        await query.edit_message_text("Я SmartAI-бот от компании SmartAI 🎨")

    elif query.data == "gen_image":
        prompt = "Фантастический пейзаж в стиле цифрового искусства"
        try:
            response = client.images.generate(
                model="gpt-image-1",
                prompt=prompt,
                size="512x512"
            )
            await query.message.reply_photo(
                photo=response.data[0].url,
                caption=f"Вот картинка:\n{prompt}"
            )
        except Exception as e:
            await query.message.reply_text(f"Ошибка: {e}")

# ====== Текст ======
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    text = message.text
    user_id = message.from_user.id

    history = user_memory.get(user_id, [])
    history.append({"role": "user", "content": text})
    history = history[-MAX_HISTORY:]

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Ты умный и дружелюбный помощник."},
                *history
            ],
            max_tokens=700
        )

        answer = response.choices[0].message.content
        history.append({"role": "assistant", "content": answer})
        user_memory[user_id] = history

        await message.reply_text(answer, reply_markup=main_keyboard())
    except Exception as e:
        await message.reply_text(f"Ошибка: {e}")

# ====== Фото ======
async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    file = await photo.get_file()
    img_bytes = await file.download_as_bytearray()

    img = Image.open(BytesIO(img_bytes))
    buf = BytesIO()
    img.save(buf, format="PNG")
    b64_image = base64.b64encode(buf.getvalue()).decode()

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Опиши изображение"},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_image}"}}
                ]
            }],
            max_tokens=800
        )

        await update.message.reply_text(response.choices[0].message.content, reply_markup=main_keyboard())
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")

# ====== Запуск ======
def main():
    # Flask в фоне
    threading.Thread(target=run_flask).start()

    # Telegram бот
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_image))

    print("🤖 Бот + Flask сервер запущены")
    app.run_polling()

if __name__ == "__main__":
    main()
