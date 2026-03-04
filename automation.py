import os
import asyncio
import logging
import pytz
from dotenv import load_dotenv
from threading import Thread
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)
from playwright.async_api import async_playwright
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ================== LOAD ENV ==================
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# ================== LOGGING ==================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ================== FLASK (FOR RENDER) ==================
web_app = Flask(__name__)

@web_app.route("/")
def home():
    return "Bot is running!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host="0.0.0.0", port=port)

# ================== STATES ==================
WAITING_FOR_NUMBER = 1

# ================== DATA STORE ==================
user_data_store = {}

scheduler = AsyncIOScheduler(timezone=pytz.timezone("Asia/Kolkata"))

# ================== START MENU ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in user_data_store:
        user_data_store[user_id] = {
            "accounts": [],
        }

    keyboard = [
        [InlineKeyboardButton("➕ Add Account", callback_data="add_account")],
        [InlineKeyboardButton("🔄 Refresh", callback_data="refresh")],
    ]

    text = (
        "🤖 *WhatsApp Web Auto-Messenger*\n\n"
        f"📱 Linked Accounts: {len(user_data_store[user_id]['accounts'])}"
    )

    if update.message:
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )
    else:
        await update.callback_query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

# ================== BUTTON HANDLER ==================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "add_account":
        await query.edit_message_text(
            "📱 Send WhatsApp number with country code.\nExample: +919876543210"
        )
        return WAITING_FOR_NUMBER

    elif query.data == "refresh":
        await start(update, context)

    return ConversationHandler.END

# ================== RECEIVE NUMBER ==================
async def receive_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    number = update.message.text
    user_id = update.effective_user.id

    await update.message.reply_text("⏳ Generating pairing code...")

    asyncio.create_task(get_whatsapp_pairing_code(number, user_id, context))

    return ConversationHandler.END

# ================== PLAYWRIGHT ==================
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

            user_data_store[user_id]["accounts"].append(number)

            await context.bot.send_message(
                chat_id=user_id,
                text=f"✅ {number} linked successfully!",
            )

            await browser.close()

    except Exception as e:
        logger.error(e)
        await context.bot.send_message(
            chat_id=user_id,
            text="❌ Login failed or timed out.",
        )

# ================== MAIN ==================
def main():
    Thread(target=run_web).start()

    if not TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN missing")
        return

    application = Application.builder().token(TOKEN).build()

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

    scheduler.start()

    print("✅ Bot Running...")
    application.run_polling()

if __name__ == "__main__":
    main()
