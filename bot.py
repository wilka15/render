import os
from aiohttp import web
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from openai import OpenAI

# ===== ENV =====
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not TELEGRAM_TOKEN or not OPENAI_API_KEY:
    raise RuntimeError("❌ TELEGRAM_BOT_TOKEN or OPENAI_API_KEY not set")

bot = Bot(token=TELEGRAM_TOKEN)
client = OpenAI(api_key=OPENAI_API_KEY)

# ===== Memory =====
user_memory = {}
MAX_HISTORY = 10

# ===== Keyboard =====
def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🧹 Очистить память", callback_data="clear"),
         InlineKeyboardButton("ℹ️ О боте", callback_data="about")]
    ])

# ===== Handlers =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Я SmartAI-бот 🤖", reply_markup=main_keyboard())

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id

    if query.data == "clear":
        user_memory[uid] = []
        await query.edit_message_text("🧹 Память очищена")

    elif query.data == "about":
        await query.edit_message_text("Я AI-бот с памятью и изображениями 🤖")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    text = update.message.text

    history = user_memory.get(uid, [])
    history.append({"role": "user", "content": text})
    history = history[-MAX_HISTORY:]

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "Ты умный ассистент"}, *history],
            max_tokens=600
        )
        answer = resp.choices[0].message.content
        history.append({"role": "assistant", "content": answer})
        user_memory[uid] = history

        await update.message.reply_text(answer, reply_markup=main_keyboard())
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")

# ===== Webhook endpoint =====
async def telegram_webhook(request):
    data = await request.json()
    update = Update.de_json(data, bot)
    app = request.app["tg_app"]
    await app.update_queue.put(update)
    return web.Response(text="ok")

async def health(request):
    return web.Response(text="✅ Bot is running")

# ===== Main =====
async def main():
    tg_app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    tg_app.add_handler(CommandHandler("start", start))
    tg_app.add_handler(CallbackQueryHandler(buttons))
    tg_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    await tg_app.initialize()

    # Web server
    app = web.Application()
    app["tg_app"] = tg_app
    app.router.add_post(f"/webhook/{TELEGRAM_TOKEN}", telegram_webhook)
    app.router.add_get("/", health)

    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 3000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    # Устанавливаем Webhook в Telegram
    url = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}/webhook/{TELEGRAM_TOKEN}"
    await bot.set_webhook(url)

    print(f"🌐 Web + Telegram webhook running on {port}")
    await asyncio.Event().wait()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
