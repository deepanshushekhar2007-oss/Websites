import asyncio
import json
import os
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

# ================= CONFIG =================

TOKEN = os.getenv("TOKEN")
OWNER_ID = 6860983540

if not TOKEN:
    raise ValueError("TOKEN not found!")

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

# ================= WEB SERVER =================

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

# ================= ADD PAIR =================

@dp.callback_query(F.data == "add_pair")
async def add_pair(call: CallbackQuery):
    user_states[call.from_user.id] = {"step": "pair_from"}
    await call.message.edit_text("Send FROM chat ID:", reply_markup=back_button())
    await call.answer()

# ================= REMOVE PAIR =================

@dp.callback_query(F.data == "remove_pair")
async def remove_pair(call: CallbackQuery):
    db = load_db()
    if not db["pairs"]:
        await call.answer("No pairs found ❌")
        return

    text = "Send index number to remove:\n\n"
    for i, p in enumerate(db["pairs"]):
        text += f"{i+1}. {p['from']} ➜ {p['to']}\n"

    user_states[call.from_user.id] = {"step": "remove_pair"}
    await call.message.edit_text(text, reply_markup=back_button())
    await call.answer()

# ================= TOGGLE PAIR =================

@dp.callback_query(F.data == "toggle_pair")
async def toggle_pair(call: CallbackQuery):
    db = load_db()
    if not db["pairs"]:
        await call.answer("No pairs found ❌")
        return

    text = "Send index number to toggle:\n\n"
    for i, p in enumerate(db["pairs"]):
        status = "ON" if p.get("enabled", True) else "OFF"
        text += f"{i+1}. {p['from']} ➜ {p['to']} ({status})\n"

    user_states[call.from_user.id] = {"step": "toggle_pair"}
    await call.message.edit_text(text, reply_markup=back_button())
    await call.answer()

# ================= STATUS =================

@dp.callback_query(F.data == "status")
async def status_panel(call: CallbackQuery):
    db = load_db()
    text = f"""
📊 <b>BOT STATUS</b>

Pairs: {len(db['pairs'])}
Buttons: {len(db['buttons'])}
Global: {"ON ✅" if db.get("global_enabled", True) else "OFF ❌"}
"""
    await call.message.edit_text(text, reply_markup=main_menu(), parse_mode="HTML")
    await call.answer()

# ================= GLOBAL =================

@dp.callback_query(F.data == "global")
async def global_toggle(call: CallbackQuery):
    db = load_db()
    db["global_enabled"] = not db.get("global_enabled", True)
    save_db(db)

    await call.answer("Toggled ✅")
    await back(call)

# ================= BUTTON MANAGER =================

def button_menu():
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Add Button", callback_data="add_button")
    kb.button(text="❌ Remove Button", callback_data="remove_button")
    kb.button(text="🔙 Back", callback_data="back")
    kb.adjust(1)
    return kb.as_markup()

@dp.callback_query(F.data == "button_manager")
async def button_manager(call: CallbackQuery):
    await call.message.edit_text("🔘 BUTTON MANAGER", reply_markup=button_menu())
    await call.answer()

@dp.callback_query(F.data == "add_button")
async def add_button(call: CallbackQuery):
    user_states[call.from_user.id] = {"step": "button_text"}
    await call.message.edit_text("Send Button Text:", reply_markup=back_button())
    await call.answer()

@dp.callback_query(F.data == "remove_button")
async def remove_button(call: CallbackQuery):
    db = load_db()
    if not db["buttons"]:
        await call.answer("No buttons ❌")
        return

    text = "Send index to remove:\n\n"
    for i, b in enumerate(db["buttons"]):
        text += f"{i+1}. {b['text']}\n"

    user_states[call.from_user.id] = {"step": "remove_button"}
    await call.message.edit_text(text, reply_markup=back_button())
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
    await call.message.edit_text("📝 START MESSAGE MANAGER", reply_markup=start_menu())
    await call.answer()

@dp.callback_query(F.data == "set_start")
async def set_start(call: CallbackQuery):
    user_states[call.from_user.id] = {"step": "set_start"}
    await call.message.edit_text("Send new start message:", reply_markup=back_button())
    await call.answer()

@dp.callback_query(F.data == "view_start")
async def view_start(call: CallbackQuery):
    db = load_db()
    text = db["start_message"] or "No start message set."
    await call.message.edit_text(text, reply_markup=start_menu())
    await call.answer()

@dp.callback_query(F.data == "remove_start")
async def remove_start(call: CallbackQuery):
    db = load_db()
    db["start_message"] = None
    save_db(db)
    await call.answer("Removed ✅")
    await start_manager(call)

# ================= MESSAGE STATE HANDLER =================

@dp.message(F.chat.type == "private")
async def private_handler(message: Message):
    uid = message.from_user.id
    if uid not in user_states:
        return

    db = load_db()
    state = user_states[uid]

    try:

        if state["step"] == "pair_from":
            user_states[uid] = {"step": "pair_to", "from": int(message.text)}
            await message.answer("Send TO chat ID:")
            return

        if state["step"] == "pair_to":
            db["pairs"].append({
                "from": state["from"],
                "to": int(message.text),
                "enabled": True
            })
            save_db(db)
            user_states.pop(uid)
            await message.answer("✅ Pair Added", reply_markup=main_menu())
            return

        if state["step"] == "remove_pair":
            index = int(message.text) - 1
            db["pairs"].pop(index)
            save_db(db)
            user_states.pop(uid)
            await message.answer("✅ Removed", reply_markup=main_menu())
            return

        if state["step"] == "toggle_pair":
            index = int(message.text) - 1
            db["pairs"][index]["enabled"] = not db["pairs"][index].get("enabled", True)
            save_db(db)
            user_states.pop(uid)
            await message.answer("✅ Toggled", reply_markup=main_menu())
            return

        if state["step"] == "button_text":
            user_states[uid] = {"step": "button_url", "text": message.text}
            await message.answer("Send Button URL:")
            return

        if state["step"] == "button_url":
            db["buttons"].append({
                "text": state["text"],
                "url": message.text
            })
            save_db(db)
            user_states.pop(uid)
            await message.answer("✅ Button Added", reply_markup=main_menu())
            return

        if state["step"] == "remove_button":
            index = int(message.text) - 1
            db["buttons"].pop(index)
            save_db(db)
            user_states.pop(uid)
            await message.answer("✅ Button Removed", reply_markup=main_menu())
            return

        if state["step"] == "set_start":
            db["start_message"] = message.text
            save_db(db)
            user_states.pop(uid)
            await message.answer("✅ Start Updated", reply_markup=main_menu())
            return

    except:
        await message.answer("Invalid input ❌")
        user_states.pop(uid)

# ================= FORWARD SYSTEM =================

def build_buttons():
    db = load_db()
    if not db["buttons"]:
        return None
    kb = InlineKeyboardBuilder()
    for b in db["buttons"]:
        kb.add(InlineKeyboardButton(text=b["text"], url=b["url"]))
    kb.adjust(1)
    return kb.as_markup()

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
            except Exception as e:
                print("Forward error:", e)

# ================= MAIN =================

async def main():
    print("🚀 Bot Starting...")
    await start_web_server()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
