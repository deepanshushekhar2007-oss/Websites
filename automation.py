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

# Load environment variables
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Setup logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# States for ConversationHandler
WAITING_FOR_NUMBER = 1
WAITING_FOR_DELAY = 2
WAITING_FOR_SCHEDULE_TIME = 3

# In-memory storage (Use a database like SQLite/PostgreSQL in production)
user_data_store = {}
# Format: { user_id: { 'accounts': [{'number': '...', 'context': ...}], 'delay': 250, 'schedule': '14:30', 'is_running': False } }

scheduler = AsyncIOScheduler(timezone=pytz.timezone('Asia/Kolkata'))
scheduler.start()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if user_id not in user_data_store:
        user_data_store[user_id] = {'accounts': [], 'delay': 250, 'schedule': None, 'is_running': False}
    
    keyboard = [
        [InlineKeyboardButton("➕ Add Account", callback_data='add_account'),
         InlineKeyboardButton("📋 List Linked Accounts", callback_data='list_accounts')],
        [InlineKeyboardButton("⏱ Set Delay", callback_data='set_delay'),
         InlineKeyboardButton("📅 Schedule (IST)", callback_data='schedule')],
        [InlineKeyboardButton("▶️ Start Messaging", callback_data='start_messaging'),
         InlineKeyboardButton("⏹ Stop", callback_data='stop')],
        [InlineKeyboardButton("🚪 Logout All", callback_data='logout')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    welcome_msg = (
        "🤖 *WhatsApp Web Auto-Messenger Bot*\n\n"
        "Welcome! This bot helps you link multiple WhatsApp accounts and send automated "
        "messages between them to keep them active.\n\n"
        "Current Settings:\n"
        f"⏱ Delay: {user_data_store[user_id]['delay']} seconds\n"
        f"📅 Schedule: {user_data_store[user_id]['schedule'] or 'Not set'} (IST)\n"
        f"📱 Linked Accounts: {len(user_data_store[user_id]['accounts'])}\n\n"
        "Choose an option below:"
    )
    if update.message:
        await update.message.reply_text(welcome_msg, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.callback_query.edit_message_text(welcome_msg, reply_markup=reply_markup, parse_mode='Markdown')

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    
    if query.data == 'add_account':
        await query.edit_message_text("Please enter your WhatsApp number with country code (e.g., +919876543210):")
        return WAITING_FOR_NUMBER
    elif query.data == 'list_accounts':
        accounts = user_data_store[user_id]['accounts']
        if not accounts:
            msg = "No accounts linked yet."
        else:
            msg = "Linked Accounts:\n" + "\n".join([f"📱 {acc['number']}" for acc in accounts])
        
        keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data='back_to_main')]]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
    elif query.data == 'set_delay':
        await query.edit_message_text("Enter minimum delay in seconds (e.g., 250). Minimum allowed is 200s:")
        return WAITING_FOR_DELAY
    elif query.data == 'schedule':
        await query.edit_message_text("Enter schedule time in IST (HH:MM) format (e.g., 14:30):")
        return WAITING_FOR_SCHEDULE_TIME
    elif query.data == 'start_messaging':
        if len(user_data_store[user_id]['accounts']) < 2:
            await query.edit_message_text("⚠️ You need at least 2 linked accounts to start messaging.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data='back_to_main')]]))
            return ConversationHandler.END
            
        await query.edit_message_text("✅ Starting messaging between accounts...", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu", callback_data='back_to_main')]]))
        user_data_store[user_id]['is_running'] = True
        asyncio.create_task(messaging_loop(user_id, context))
    elif query.data == 'stop':
        user_data_store[user_id]['is_running'] = False
        await query.edit_message_text("⏹ Messaging stopped.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu", callback_data='back_to_main')]]))
    elif query.data == 'logout':
        user_data_store[user_id]['accounts'] = []
        await query.edit_message_text("🚪 Logged out from all accounts.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu", callback_data='back_to_main')]]))
    elif query.data == 'back_to_main':
        await start(update, context)
    
    return ConversationHandler.END

async def receive_number(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    number = update.message.text
    user_id = update.effective_user.id
    await update.message.reply_text(f"⏳ Processing number {number}. Opening WhatsApp Web and generating pairing code... This might take a minute.")
    
    # Run playwright in background to get pairing code
    asyncio.create_task(get_whatsapp_pairing_code(number, user_id, context))
    return ConversationHandler.END

async def get_whatsapp_pairing_code(number, user_id, context):
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            browser_context = await browser.new_context()
            page = await browser_context.new_page()
            
            await page.goto("https://web.whatsapp.com/")
            
            # Click "Link with phone number"
            await page.wait_for_selector("span[role='button']:has-text('Link with phone number')", timeout=60000)
            await page.click("span[role='button']:has-text('Link with phone number')")
            
            # Enter phone number
            await page.wait_for_selector('input[type="text"]')
            await page.fill('input[type="text"]', number)
            await page.click("div[role='button']:has-text('Next')")
            
            # Extract pairing code
            await page.wait_for_selector('div[data-testid="pairing-code"]', timeout=30000)
            code_element = await page.query_selector('div[data-testid="pairing-code"]')
            code = await code_element.inner_text()
            
            await context.bot.send_message(chat_id=user_id, text=f"🔑 Your pairing code for {number} is:\n\n*{code}*\n\nPlease enter this on your phone's WhatsApp -> Linked Devices.", parse_mode='Markdown')
            
            # Wait for login to complete (chat list appears)
            await page.wait_for_selector('div[data-testid="chat-list"]', timeout=120000)
            
            # Save session state (simplified for this example)
            user_data_store[user_id]['accounts'].append({
                'number': number,
                'context': browser_context # In a real app, save storage_state to disk
            })
            await context.bot.send_message(chat_id=user_id, text=f"✅ Account {number} linked successfully!")
            
    except Exception as e:
        logger.error(f"Error linking account: {e}")
        await context.bot.send_message(chat_id=user_id, text="❌ Failed to get pairing code or login timed out. Please try again.")

async def receive_delay(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        delay = int(update.message.text)
        if delay < 200:
            await update.message.reply_text("⚠️ Delay should be at least 200 seconds to prevent bans. Setting to 200.")
            delay = 200
        user_data_store[update.effective_user.id]['delay'] = delay
        await update.message.reply_text(f"✅ Delay set to {delay} seconds.")
    except ValueError:
        await update.message.reply_text("❌ Invalid number. Please try again.")
    await start(update, context)
    return ConversationHandler.END

async def receive_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    time_str = update.message.text
    user_id = update.effective_user.id
    try:
        # Validate time format
        datetime.strptime(time_str, '%H:%M')
        user_data_store[user_id]['schedule'] = time_str
        
        # Schedule the job
        hour, minute = map(int, time_str.split(':'))
        job_id = f"job_{user_id}"
        
        # Remove existing job if any
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)
            
        scheduler.add_job(
            scheduled_messaging,
            'cron',
            hour=hour,
            minute=minute,
            id=job_id,
            args=[user_id, context]
        )
        
        await update.message.reply_text(f"✅ Schedule set to {time_str} IST.")
    except ValueError:
        await update.message.reply_text("❌ Invalid time format. Please use HH:MM (e.g., 14:30).")
        
    await start(update, context)
    return ConversationHandler.END

async def scheduled_messaging(user_id, context):
    user_data_store[user_id]['is_running'] = True
    await context.bot.send_message(chat_id=user_id, text="⏰ Scheduled messaging started!")
    await messaging_loop(user_id, context)

async def messaging_loop(user_id, context):
    user_data = user_data_store.get(user_id)
    if not user_data or len(user_data['accounts']) < 2:
        return

    accounts = user_data['accounts']
    delay = user_data['delay']
    
    messages = [
        "Hello!", "How are you?", "Just checking in.", "Have a great day!", 
        "What's up?", "Good to see you.", "Testing connection.", 
        "All good here.", "Hope you are well.", "Catch you later!"
    ]
    
    while user_data_store[user_id].get('is_running', False):
        try:
            # Pick random 5 to 10 messages per cycle
            num_msgs = random.randint(5, 10)
            await context.bot.send_message(chat_id=user_id, text=f"🔄 Starting cycle: Sending {num_msgs} messages.")
            
            for _ in range(num_msgs):
                if not user_data_store[user_id].get('is_running', False):
                    break
                
                # Pick two distinct accounts for two-sided messaging
                sender, receiver = random.sample(accounts, 2)
                msg_text = random.choice(messages)
                
                # In a full implementation, use Playwright to navigate to the chat and send the message
                # Example placeholder:
                # page = await sender['context'].new_page()
                # await page.goto(f"https://web.whatsapp.com/send?phone={receiver['number']}&text={msg_text}")
                # await page.click('span[data-icon="send"]')
                
                logger.info(f"Simulated: Sending message from {sender['number']} to {receiver['number']}: {msg_text}")
                
                # Wait for the user-defined delay between messages
                await asyncio.sleep(delay)
                
        except Exception as e:
            logger.error(f"Error in messaging loop: {e}")
            await asyncio.sleep(60)

def main():
    if not TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is not set in .env file.")
        return

    application = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start),
            CallbackQueryHandler(button_handler)
        ],
        states={
            WAITING_FOR_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_number)],
            WAITING_FOR_DELAY: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_delay)],
            WAITING_FOR_SCHEDULE_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_schedule)],
        },
        fallbacks=[CommandHandler('start', start)],
    )

    application.add_handler(conv_handler)
    logger.info("Bot is running...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
