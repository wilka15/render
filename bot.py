import os
import base64
from io import BytesIO
from PIL import Image
from dotenv import load_dotenv

from aiohttp import web
import asyncio

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

from openai import OpenAI

# ====== ENV ======
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

client = OpenAI(api_key=OPENAI_API_KEY)

# ====== Memory ======
user_memory = {}
MAX_HISTORY = 10

# ====== Keyboard ======
def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🧹 Очистить память", callback_data="clear"),
         InlineKeyboardButton("ℹ️ О боте", callback_data="about")],
        [InlineKeyboardButton("🎨 Сгенерировать картинку", callback_data="gen_image")]
    ])

# ====== Telegram handlers ======
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Я SmartAI-бот!", reply_markup=main_keyboard())

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id

    if query.data == "clear":
        user_memory[uid] = []
        await query.edit_message_text("🧹 Память очищена")

    elif query.data == "about":
        await query.edit_message_text("Я GPT-бот с памятью и изображениями")

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
            max_tokens=600
        )

        answer = resp.choices[0].message.content
        history.append({"role": "assistant", "content": answer})
        user_memory[uid] = history

        await update.message.reply_text(answer, reply_markup=main_keyboard())
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")

# ====== AIOHTTP SERVER ======
async def health(request):
    return web.Response(text="✅ Bot is running")

async def main():
    # Telegram
    tg_app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    tg_app.add_handler(CommandHandler("start", start))
    tg_app.add_handler(CallbackQueryHandler(buttons))
    tg_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    await tg_app.initialize()
    await tg_app.start()
    await tg_app.bot.initialize()

    # Web server
    app = web.Application()
    app.router.add_get("/", health)

    runner = web.AppRunner(app)
    await runner.setup()

    port = int(os.environ.get("PORT", 3000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    print(f"🚀 Bot + Web running on {port}")

    # Run forever
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
