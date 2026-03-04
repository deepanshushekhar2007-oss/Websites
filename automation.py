import os
import asyncio
import random
import logging
from datetime import datetime
import pytz
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)
from playwright.async_api import async_playwright
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ================== WEB SERVER (FOR RENDER PORT) ==================
from flask import Flask
from threading import Thread

app_web = Flask(__name__)

@app_web.route("/")
def home():
    return "Bot is running!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app_web.run(host="0.0.0.0", port=port)
# ================================================================

# Load environment variables
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

WAITING_FOR_NUMBER = 1
WAITING_FOR_DELAY = 2
WAITING_FOR_SCHEDULE_TIME = 3

user_data_store = {}

scheduler = AsyncIOScheduler(timezone=pytz.timezone('Asia/Kolkata'))


# ================= TELEGRAM BOT =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in user_data_store:
        user_data_store[user_id] = {
            'accounts': [],
            'delay': 250,
            'schedule': None,
            'is_running': False
        }

    keyboard = [
        [InlineKeyboardButton("➕ Add Account", callback_data='add_account'),
         InlineKeyboardButton("📋 List Linked Accounts", callback_data='list_accounts')],
        [InlineKeyboardButton("⏱ Set Delay", callback_data='set_delay'),
         InlineKeyboardButton("📅 Schedule (IST)", callback_data='schedule')],
        [InlineKeyboardButton("▶️ Start Messaging", callback_data='start_messaging'),
         InlineKeyboardButton("⏹ Stop", callback_data='stop')],
        [InlineKeyboardButton("🚪 Logout All", callback_data='logout')]
    ]

    msg = (
        "🤖 *WhatsApp Web Auto-Messenger Bot*\n\n"
        f"⏱ Delay: {user_data_store[user_id]['delay']} sec\n"
        f"📅 Schedule: {user_data_store[user_id]['schedule'] or 'Not set'}\n"
        f"📱 Linked Accounts: {len(user_data_store[user_id]['accounts'])}"
    )

    if update.message:
        await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    else:
        await update.callback_query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")


async def get_whatsapp_pairing_code(number, user_id, context):
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"]
            )

            browser_context = await browser.new_context()
            page = await browser_context.new_page()

            await page.goto("https://web.whatsapp.com/")
            await page.wait_for_selector("span:has-text('Link with phone number')", timeout=60000)
            await page.click("span:has-text('Link with phone number')")

            await page.wait_for_selector('input[type="text"]')
            await page.fill('input[type="text"]', number)
            await page.click("div[role='button']:has-text('Next')")

            await page.wait_for_selector('div[data-testid="pairing-code"]', timeout=30000)
            code = await page.inner_text('div[data-testid="pairing-code"]')

            await context.bot.send_message(
                chat_id=user_id,
                text=f"🔑 Pairing code for {number}:\n\n*{code}*",
                parse_mode="Markdown"
            )

            await page.wait_for_selector('div[data-testid="chat-list"]', timeout=120000)

            user_data_store[user_id]['accounts'].append({
                'number': number,
                'context': browser_context
            })

            await context.bot.send_message(chat_id=user_id, text=f"✅ {number} linked successfully!")

    except Exception as e:
        logger.error(e)
        await context.bot.send_message(chat_id=user_id, text="❌ Login failed or timed out.")


# ================= ASYNC MAIN =================

async def async_main():
    Thread(target=run_web).start()  # Start Flask server for Render

    if not TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN missing")
        return

    application = Application.builder().token(TOKEN).build()

    scheduler.start()

    application.add_handler(CommandHandler("start", start))

    logger.info("Bot Running...")

    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    await application.updater.idle()


if __name__ == "__main__":
    asyncio.run(async_main())
