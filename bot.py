import os
import base64
from io import BytesIO
from PIL import Image
from dotenv import load_dotenv

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
        "Привет! Я SmartAI-бот! 🎨\n"
        "Пиши мне или упоминай меня в группе через @.",
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
        await query.edit_message_text(
            "Я GPT-бот с памятью, кнопками и генерацией изображений 🎨"
        )

    elif query.data == "gen_image":
        prompt = "Фантастический пейзаж в стиле цифрового искусства"
        try:
            response = client.images.generate(
                model="gpt-image-1",
                prompt=prompt,
                size="512x512"
            )
            image_url = response.data[0].url
            await query.message.reply_photo(photo=image_url, caption=f"Вот картинка по промпту:\n{prompt}")
        except Exception as e:
            await query.message.reply_text(f"Ошибка при генерации картинки: {e}")

# ====== Работа с текстом ======
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    chat = message.chat
    text = message.text
    user_id = message.from_user.id
    bot_username = context.bot.username
    bot_id = context.bot.id

    # ===== Логика групп =====
    if chat.type in ["group", "supergroup"]:
        mentioned = False
        if message.entities:
            for entity in message.entities:
                if entity.type == "mention":
                    mention_text = text[entity.offset: entity.offset + entity.length]
                    if mention_text.lower() == f"@{bot_username.lower()}":
                        mentioned = True
                        break
        replied_to_bot = (
            message.reply_to_message
            and message.reply_to_message.from_user
            and message.reply_to_message.from_user.id == bot_id
        )
        if not mentioned and not replied_to_bot:
            return
        text = text.replace(f"@{bot_username}", "").strip()

    # ===== Память =====
    history = user_memory.get(user_id, [])
    history.append({"role": "user", "content": text})
    history = history[-MAX_HISTORY:]

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Ты полезный, умный и дружелюбный ассистент."},
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

# ====== Работа с изображениями ======
async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        await update.message.reply_text(answer, reply_markup=main_keyboard())
    except Exception as e:
        await update.message.reply_text(f"Ошибка с изображением: {e}")

# ====== Запуск бота ======
def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_image))

    print("🤖 Бот запущен")
    app.run_polling()

if __name__ == "__main__":
    main()
