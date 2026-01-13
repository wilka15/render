import os
import base64
from io import BytesIO
from PIL import Image
from dotenv import load_dotenv

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters
)

from openai import OpenAI

# ====== Загрузка ключей ======
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

client = OpenAI(api_key=OPENAI_API_KEY)

# ====== Память ======
user_memory = {}
bot_messages = {}

MAX_HISTORY = 10

# ====== Клавиатура ======
def main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton("🗑 Очистить чат"), KeyboardButton("ℹ️ О боте")],
            [KeyboardButton("🎨 Сгенерировать картинку")]
        ],
        resize_keyboard=True
    )

# ====== /start ======
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я SmartAI-бот 🤖\nПиши сообщение или используй кнопки ниже.",
        reply_markup=main_keyboard()
    )

# ====== Текст ======
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.message.from_user.id

    # ===== Очистка чата =====
    if text == "🗑 Очистить чат":
        user_memory[user_id] = []

        # Удаляем последние сообщения бота
        if user_id in bot_messages:
            for msg_id in bot_messages[user_id][-20:]:
                try:
                    await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=msg_id)
                except:
                    pass

        sent = await update.message.reply_text("🧹 Чат очищен!", reply_markup=main_keyboard())
        bot_messages.setdefault(user_id, []).append(sent.message_id)
        return

    # ===== О боте =====
    if text == "ℹ️ О боте":
        sent = await update.message.reply_text(
            "Я GPT-бот с памятью, кнопками и генерацией изображений 🎨",
            reply_markup=main_keyboard()
        )
        bot_messages.setdefault(user_id, []).append(sent.message_id)
        return

    # ===== Генерация картинки =====
    if text == "🎨 Сгенерировать картинку":
        prompt = "Фантастический пейзаж в стиле цифрового искусства"
        try:
            response = client.images.generate(
                model="gpt-image-1",
                prompt=prompt,
                size="512x512"
            )
            image_url = response.data[0].url
            sent = await update.message.reply_photo(
                photo=image_url,
                caption=f"Вот изображение:\n{prompt}",
                reply_markup=main_keyboard()
            )
            bot_messages.setdefault(user_id, []).append(sent.message_id)
        except Exception as e:
            sent = await update.message.reply_text(f"Ошибка: {e}")
            bot_messages.setdefault(user_id, []).append(sent.message_id)
        return

    # ===== Обычный диалог =====
    history = user_memory.get(user_id, [])
    history.append({"role": "user", "content": text})
    history = history[-MAX_HISTORY:]

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Ты умный, дружелюбный помощник."},
                *history
            ],
            max_tokens=700
        )

        answer = response.choices[0].message.content
        history.append({"role": "assistant", "content": answer})
        user_memory[user_id] = history

        sent = await update.message.reply_text(answer, reply_markup=main_keyboard())
        bot_messages.setdefault(user_id, []).append(sent.message_id)

    except Exception as e:
        sent = await update.message.reply_text(f"Ошибка: {e}")
        bot_messages.setdefault(user_id, []).append(sent.message_id)

# ====== Фото ======
async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    photo = update.message.photo[-1]
    file = await photo.get_file()
    img_bytes = await file.download_as_bytearray()

    img = Image.open(BytesIO(img_bytes))
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    b64_image = base64.b64encode(buffered.getvalue()).decode()

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Опиши изображение подробно"},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_image}"}}
                ]
            }],
            max_tokens=800
        )

        answer = response.choices[0].message.content
        sent = await update.message.reply_text(answer, reply_markup=main_keyboard())
        bot_messages.setdefault(user_id, []).append(sent.message_id)

    except Exception as e:
        sent = await update.message.reply_text(f"Ошибка с изображением: {e}")
        bot_messages.setdefault(user_id, []).append(sent.message_id)

# ====== Запуск ======
def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_image))

    print("🤖 Бот запущен")
    app.run_polling()

if __name__ == "__main__":
    main()
