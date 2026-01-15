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

# ===== Load ENV =====
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not TELEGRAM_TOKEN or not OPENAI_API_KEY:
    raise RuntimeError("❌ TELEGRAM_BOT_TOKEN or OPENAI_API_KEY not set")

client = OpenAI(api_key=OPENAI_API_KEY)

# ===== Memory =====
user_memory = {}
MAX_HISTORY = 10

# ===== Keyboard =====
def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🧹 Очистить память", callback_data="clear"),
         InlineKeyboardButton("ℹ️ О боте", callback_data="about")],
        [InlineKeyboardButton("🎨 Сгенерировать картинку", callback_data="gen_image")]
    ])

# ===== Handlers =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я SmartAI-бот! 🎨\nПиши мне или упоминай меня в группе через @.",
        reply_markup=main_keyboard()
    )

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id

    if query.data == "clear":
        user_memory[uid] = []
        await query.edit_message_text("🧹 Память очищена!")

    elif query.data == "about":
        await query.edit_message_text("Я GPT-бот с памятью и генерацией изображений 🎨")

    elif query.data == "gen_image":
        prompt = "Фантастический пейзаж в стиле цифрового искусства"
        try:
            resp = client.images.generate(model="gpt-image-1", prompt=prompt, size="512x512")
            url = resp.data[0].url
            await query.message.reply_photo(photo=url, caption=f"Вот картинка по промпту:\n{prompt}")
        except Exception as e:
            await query.message.reply_text(f"Ошибка генерации картинки: {e}")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    text = update.message.text

    history = user_memory.get(uid, [])
    history.append({"role": "user", "content": text})
    history = history[-MAX_HISTORY:]

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "Ты полезный ассистент"}, *history],
            max_tokens=700
        )
        answer = resp.choices[0].message.content
        history.append({"role": "assistant", "content": answer})
        user_memory[uid] = history

        await update.message.reply_text(answer, reply_markup=main_keyboard())
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")

async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    file = await photo.get_file()
    img_bytes = await file.download_as_bytearray()
    img = Image.open(BytesIO(img_bytes))

    buffered = BytesIO()
    img.save(buffered, format="PNG")
    b64_image = base64.b64encode(buffered.getvalue()).decode()

    try:
        resp = client.chat.completions.create(
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
        answer = resp.choices[0].message.content
        await update.message.reply_text(answer, reply_markup=main_keyboard())
    except Exception as e:
        await update.message.reply_text(f"Ошибка с изображением: {e}")

# ===== Main =====
def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_image))

    print("🤖 Бот запущен (используем polling)")
    app.run_polling()

if __name__ == "__main__":
    main()
