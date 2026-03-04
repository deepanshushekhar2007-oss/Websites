import asyncio
import json
import os
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

# ================= CONFIG =================

TOKEN = os.getenv("TOKEN")  # Render ENV variable
OWNER_ID = 6860983540

if not TOKEN:
    raise ValueError("TOKEN not found! Set it in Render Environment Variables.")

bot = Bot(token=TOKEN)
dp = Dispatcher()

DB_FILE = "db.json"
user_states = {}

# ================= DATABASE =================

def load_db():
    if not os.path.exists(DB_FILE):
        return {
            "admins": [],
            "pairs": [],
            "buttons": [],
            "start_message": None,
            "global_enabled": True
        }
    with open(DB_FILE, "r") as f:
        return json.load(f)

def save_db(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=4)

def is_admin(user_id):
    db = load_db()
    return user_id == OWNER_ID or user_id in db["admins"]

# ================= WEB SERVER (RENDER FIX) =================

async def homepage(request):
    return web.Response(text="Bot is running 🚀")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", homepage)

    port = int(os.environ.get("PORT", 10000))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"🌐 Web server started on port {port}")

# ================= MENUS =================

def main_menu():
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Add Pair", callback_data="add_pair")
    kb.button(text="❌ Remove Pair", callback_data="remove_pair")
    kb.button(text="🔁 Toggle Pair", callback_data="toggle_pair")
    kb.button(text="📊 Status", callback_data="status")
    kb.button(text="🌐 Global ON/OFF", callback_data="global")
    kb.button(text="🔘 Button Manager", callback_data="button_manager")
    kb.button(text="📝 Start Msg Manager", callback_data="start_manager")
    kb.adjust(2)
    return kb.as_markup()

def back_button():
    kb = InlineKeyboardBuilder()
    kb.button(text="🔙 Back", callback_data="back")
    return kb.as_markup()

# ================= START =================

@dp.message(Command("start"))
async def start_cmd(message: Message):
    db = load_db()

    if is_admin(message.from_user.id):
        await message.answer(
            "🚀 <b>FORWARD BOT CONTROL PANEL</b>",
            reply_markup=main_menu(),
            parse_mode="HTML"
        )
        return

    if db.get("start_message"):
        await message.answer(db["start_message"])
    else:
        await message.answer("👋 Welcome!")

@dp.callback_query(F.data == "back")
async def back(call: CallbackQuery):
    await call.message.edit_text(
        "🚀 <b>FORWARD BOT CONTROL PANEL</b>",
        reply_markup=main_menu(),
        parse_mode="HTML"
    )
    await call.answer()

# ================= START MESSAGE MANAGER =================

def start_menu():
    kb = InlineKeyboardBuilder()
    kb.button(text="📝 Set Start Message", callback_data="set_start")
    kb.button(text="👀 View Start Message", callback_data="view_start")
    kb.button(text="❌ Remove Start Message", callback_data="remove_start")
    kb.button(text="🔙 Back", callback_data="back")
    kb.adjust(1)
    return kb.as_markup()

@dp.callback_query(F.data == "start_manager")
async def start_manager(call: CallbackQuery):
    await call.message.edit_text(
        "📝 <b>START MESSAGE MANAGER</b>",
        reply_markup=start_menu(),
        parse_mode="HTML"
    )
    await call.answer()

@dp.callback_query(F.data == "set_start")
async def set_start(call: CallbackQuery):
    user_states[call.from_user.id] = {"step": "set_start"}
    await call.message.edit_text(
        "Send new Start Message:",
        reply_markup=back_button()
    )
    await call.answer()

@dp.message(F.chat.type == "private")
async def private_handler(message: Message):
    uid = message.from_user.id
    if uid not in user_states:
        return

    state = user_states[uid]
    db = load_db()

    if state["step"] == "set_start":
        db["start_message"] = message.text
        save_db(db)
        user_states.pop(uid)
        await message.answer("✅ Start Message Updated", reply_markup=main_menu())
        return

@dp.callback_query(F.data == "view_start")
async def view_start(call: CallbackQuery):
    db = load_db()

    if db.get("start_message"):
        text = f"📢 Current Start Message:\n\n{db['start_message']}"
    else:
        text = "No Start Message Set."

    await call.message.edit_text(text, reply_markup=start_menu())
    await call.answer()

@dp.callback_query(F.data == "remove_start")
async def remove_start(call: CallbackQuery):
    db = load_db()
    db["start_message"] = None
    save_db(db)

    await call.answer("Removed ✅")
    await start_manager(call)

# ================= BUTTON SYSTEM =================

def build_buttons():
    db = load_db()
    if not db["buttons"]:
        return None

    kb = InlineKeyboardBuilder()
    for b in db["buttons"]:
        kb.add(InlineKeyboardButton(text=b["text"], url=b["url"]))
    kb.adjust(1)
    return kb.as_markup()

# ================= FORWARD SYSTEM =================

@dp.message(F.chat.type.in_(["group", "supergroup"]))
async def forward_handler(message: Message):
    db = load_db()

    if not db.get("global_enabled", True):
        return

    for pair in db.get("pairs", []):
        if not pair.get("enabled", True):
            continue

        if message.chat.id == pair["from"]:
            try:
                await bot.copy_message(
                    chat_id=pair["to"],
                    from_chat_id=message.chat.id,
                    message_id=message.message_id,
                    reply_markup=build_buttons()
                )
                print("✅ Forwarded with Buttons")
            except Exception as e:
                print("❌ Error:", e)

# ================= MAIN =================

async def main():
    print("🚀 Bot Starting...")
    await start_web_server()   # Render port binding
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())