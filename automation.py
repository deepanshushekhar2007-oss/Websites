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

# ================= WEB SERVER FOR RENDER =================
from flask import Flask
from threading import Thread

web_app = Flask(__name__)

@web_app.route("/")
def home():
    return "Bot is running!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host="0.0.0.0", port=port)
# ==========================================================

# Load ENV
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

WAITING_FOR_NUMBER = 1
WAITING_FOR_DELAY = 2
WAITING_FOR_SCHEDULE_TIME = 3

user_data_store = {}
scheduler = AsyncIOScheduler(timezone=pytz.timezone("Asia/Kolkata"))

# ================= START MENU =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in user_data_store:
        user_data_store[user_id] = {
            "accounts": [],
            "delay": 250,
            "schedule": None,
            "is_running": False,
        }

    keyboard = [
        [InlineKeyboardButton("➕ Add Account", callback_data="add_account")],
        [InlineKeyboardButton("🔙 Refresh", callback_data="refresh")]
    ]

    msg = (
        "🤖 *WhatsApp Web Auto-Messenger Bot*\n\n"
        f"📱 Linked Accounts: {len(user_data_store[user_id]['accounts'])}\n"
        f"⏱ Delay: {user_data_store[user_id]['delay']} sec\n"
        f"📅 Schedule: {user_data_store[user_id]['schedule'] or 'Not set'}"
    )

    if update.message:
        await update.message.reply_text(
            msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
        )
    else:
        await update.callback_query.edit_message_text(
            msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
        )

# ================= BUTTON HANDLER =================

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    if query.data == "add_account":
        await query.edit_message_text(
            "📱 Send your WhatsApp number with country code.\nExample: +919876543210"
        )
        return WAITING_FOR_NUMBER

    elif query.data == "refresh":
        await start(update, context)

    return ConversationHandler.END

# ================= RECEIVE NUMBER =================

async def receive_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    number = update.message.text
    user_id = update.effective_user.id

    await update.message.reply_text("⏳ Generating pairing code...")

    asyncio.create_task(get_whatsapp_pairing_code(number, user_id, context))
    return ConversationHandler.END

# ================= PLAYWRIGHT LOGIN =================

async def get_whatsapp_pairing_code(number, user_id, context):
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )

            browser_context = await browser.new_context()
            page = await browser_context.new_page()

            await page.goto("https://web.whatsapp.com/")
            await page.wait_for_selector("span:has-text('Link with phone number')", timeout=60000)
            await page.click("span:has-text('Link with phone number')")

            await page.wait_for_selector("input[type='text']")
            await page.fill("input[type='text']", number)
            await page.click("div[role='button']:has-text('Next')")

            await page.wait_for_selector("div[data-testid='pairing-code']", timeout=30000)
            code = await page.inner_text("div[data-testid='pairing-code']")

            await context.bot.send_message(
                chat_id=user_id,
                text=f"🔑 Pairing Code:\n\n*{code}*",
                parse_mode="Markdown",
            )

            await page.wait_for_selector("div[data-testid='chat-list']", timeout=120000)

            user_data_store[user_id]["accounts"].append(
                {"number": number, "context": browser_context}
            )

            await context.bot.send_message(
                chat_id=user_id,
                text=f"✅ Account {number} linked successfully!",
            )

    except Exception as e:
        logger.error(e)
        await context.bot.send_message(
            chat_id=user_id, text="❌ Login failed or timed out."
        )

# ================= MAIN =================

async def async_main():
    Thread(target=run_web).start()

    if not TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN missing")
        return

    application = Application.builder().token(TOKEN).build()

    scheduler.start()

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CallbackQueryHandler(button_handler),
        ],
        states={
            WAITING_FOR_NUMBER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_number)
            ],
        },
        fallbacks=[CommandHandler("start", start)],
    )

    application.add_handler(conv_handler)

    logger.info("Bot Running...")
    await application.run_polling()

if __name__ == "__main__":
    asyncio.run(async_main())
