import os
import base64
import asyncio
from io import BytesIO
from PIL import Image
from dotenv import load_dotenv
from aiohttp import web

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

from openai import OpenAI

# ===== ENV =====
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not TELEGRAM_TOKEN:
    raise RuntimeError("❌ TELEGRAM_BOT_TOKEN not set")

if not OPENAI_API_KEY:
    raise RuntimeError("❌ OPENAI_API_KEY not set")

client = OpenAI(api_key=OPENAI_API_KEY)

# ===== Memory =====
user_memory = {}
MAX_HISTORY = 10

# ===== Keyboard =====
def main_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🧹 Очистить память", callback_data="clear"),
            InlineKeyboardButton("ℹ️ О боте", callback_data="about")
        ],
        [
            InlineKeyboardButton("🎨 Сгенерировать картинку", callback_data="gen_image")
        ]
    ])

# ===== Handlers =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я SmartAI-бот 🤖",
        reply_markup=main_keyboard()
    )

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id

    if query.data == "clear":
        user_memory[uid] = []
        await query.edit_message_text("🧹 Память очищена")

    elif query.data == "about":
        await query.edit_message_text("Я AI-бот от SmartAI 🤖")

    elif query.data == "gen_image":
        prompt = "Фантастический киберпанк-город ночью"
        try:
            img = client.images.generate(
                model="gpt-image-1",
                prompt=prompt,
                size="512x512"
            )
            await query.message.reply_photo(
                photo=img.data[0].url,
                caption=f"🎨 {prompt}"
            )
        except Exception as e:
            await query.message.reply_text(f"Ошибка: {e}")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    text = update.message.text

    history = user_memory.get(uid, [])
    history.append({"role": "user", "content": text})
    history = history[-MAX_HISTORY:]

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Ты умный, полезный и дружелюбный ассистент."},
                *history
            ],
            max_tokens=600
        )

        answer = resp.choices[0].message.content
        history.append({"role": "assistant", "content": answer})
        user_memory[uid] = history

        await update.message.reply_text(answer, reply_markup=main_keyboard())

    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")

# ===== Web =====
async def health(request):
    return web.Response(text="✅ Bot is running")

# ===== Main =====
async def main():
    tg_app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    tg_app.add_handler(CommandHandler("start", start))
    tg_app.add_handler(CallbackQueryHandler(buttons))
    tg_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # Запускаем Telegram polling в фоне
    async def run_bot():
        await tg_app.initialize()
        await tg_app.start()
        await tg_app.run_polling()

    asyncio.create_task(run_bot())

    print("🤖 Telegram bot started")

    # Web server для Render
    app = web.Application()
    app.router.add_get("/", health)

    runner = web.AppRunner(app)
    await runner.setup()

    port = int(os.environ.get("PORT", 3000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    print(f"🌐 Web server running on port {port}")

    # Держим процесс живым
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
