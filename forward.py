import asyncio
import json
import os
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URI = os.getenv("MONGO_URI")

mongo_client = AsyncIOMotorClient(MONGO_URI)

db = mongo_client["forward_bot"]
config_collection = db["forward_config"]

# ================= CONFIG =================

TOKEN = os.getenv("TOKEN")  # Render ENV variable
OWNER_ID = 6860983540

if not TOKEN:
    raise ValueError("TOKEN not found! Set it in Render Environment Variables.")

bot = Bot(token=TOKEN)
dp = Dispatcher()

user_states = {}

# ================= DATABASE =================

async def load_db():

    data = await config_collection.find_one({"_id": "main"})

    if not data:

        data = {
            "_id": "main",
            "admins": [],
            "pairs": [],
            "buttons": [],
            "start_message": None,
            "global_enabled": True
        }

        await config_collection.insert_one(data)

    return data


async def save_db(data):

    await config_collection.update_one(
        {"_id": "main"},
        {"$set": data},
        upsert=True
    )


async def is_admin(user_id):

    data = await load_db()

    return user_id == OWNER_ID or user_id in data["admins"]

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
    kb.button(text="✏ Rename Pair", callback_data="rename_pair")
    kb.button(text="⏱ Auto Delete Time", callback_data="delete_time")
    kb.button(text="🔗 Link Filter", callback_data="link_filter")
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
    db = await load_db()

    if await is_admin(message.from_user.id):
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
    
@dp.callback_query(F.data == "rename_pair")
async def rename_pair_menu(call: CallbackQuery):

    db = await load_db()
    kb = InlineKeyboardBuilder()

    for i,pair in enumerate(db["pairs"]):

        name = pair.get("name", f"{pair['from']} ➜ {pair['to']}")

        kb.button(
            text=name,
            callback_data=f"rename_{i}"
        )

    kb.button(text="🔙 Back",callback_data="back")
    kb.adjust(1)

    await call.message.edit_text(
        "Select pair to rename",
        reply_markup=kb.as_markup()
    )


@dp.callback_query(F.data.startswith("rename_"))
async def rename_select(call: CallbackQuery):

    index = int(call.data.split("_")[1])

    user_states[call.from_user.id] = {
        "step":"rename_pair",
        "pair_index":index
    }

    await call.message.edit_text("Send new name")
    
@dp.message(F.chat.type == "private")
async def private_handler(message: Message):
    uid = message.from_user.id
    if uid not in user_states:
        return

    state = user_states[uid]
    db = await load_db()

    if state["step"] == "set_start":
        db["start_message"] = message.text
        await save_db(db)
        user_states.pop(uid)
        await message.answer("✅ Start Message Updated", reply_markup=main_menu())
        return
        
    if state["step"] == "rename_pair":

        index = state["pair_index"]

        db["pairs"][index]["name"] = message.text

        await save_db(db)

        user_states.pop(uid)

        await message.answer("✅ Pair Renamed",     reply_markup=main_menu())


    # AUTO DELETE SET
    if state["step"] == "set_delete_time":

        try:
            t = int(message.text)
        except:
            await message.answer("❌ Send number only")
            return

        index = state["pair_index"]

        db["pairs"][index]["delete_time"] = t

        await save_db(db)

        user_states.pop(uid)

        if t == 0:
            msg = "❌ Auto Delete Disabled"
        else:
            msg = f"✅ Auto Delete Set Successfully\n⏱ Time : {t} seconds"

        await message.answer(msg,     reply_markup=main_menu())
        
        
@dp.callback_query(F.data == "view_start")
async def view_start(call: CallbackQuery):
    db = await load_db()

    if db.get("start_message"):
        text = f"📢 Current Start Message:\n\n{db['start_message']}"
    else:
        text = "No Start Message Set."

    await call.message.edit_text(text, reply_markup=start_menu())
    await call.answer()

@dp.callback_query(F.data == "remove_start")
async def remove_start(call: CallbackQuery):
    db = await load_db()
    db["start_message"] = None
    await save_db(db)

    await call.answer("Removed ✅")
    await start_manager(call)



@dp.callback_query(F.data == "link_filter")
async def link_filter_menu(call: CallbackQuery):

    db = await load_db()
    kb = InlineKeyboardBuilder()

    for i,pair in enumerate(db["pairs"]):

        status = "ON" if pair.get("link_filter") else "OFF"

        name = pair.get("name",f"{pair['from']} ➜ {pair['to']}")

        kb.button(
            text=f"{name} ({status})",
            callback_data=f"link_{i}"
        )

    kb.button(text="🔙 Back",callback_data="back")
    kb.adjust(1)

    await call.message.edit_text(
        "Toggle Link Filter",
        reply_markup=kb.as_markup()
    )
    
    
    
@dp.callback_query(F.data.startswith("link_"))
async def link_toggle(call: CallbackQuery):

    db = await load_db()

    index = int(call.data.split("_")[1])

    db["pairs"][index]["link_filter"] = not db["pairs"][index].get("link_filter",False)

    await save_db(db)

    await call.answer("Updated")

    await link_filter_menu(call)
    
# ================= AUTO DELETE MENU =================

@dp.callback_query(F.data == "delete_time")
async def delete_time_menu(call: CallbackQuery):

    db = await load_db()
    kb = InlineKeyboardBuilder()

    if not db["pairs"]:
        await call.answer("No pairs added", show_alert=True)
        return

    for i, pair in enumerate(db["pairs"]):

        t = pair.get("delete_time", 0)

        status = "OFF" if t == 0 else f"{t}s"

        name = pair.get("name", f"{pair['from']} ➜ {pair['to']}")

        kb.button(
            text=f"{name} ({status})",
            callback_data=f"set_dtime_{i}"
        )

    kb.button(text="🔙 Back", callback_data="back")
    kb.adjust(1)

    await call.message.edit_text(
        "⏱ Select Pair to Set Delete Time",
        reply_markup=kb.as_markup()
    )
    
@dp.callback_query(F.data.startswith("set_dtime_"))
async def ask_delete_time(call: CallbackQuery):

    index = int(call.data.split("_")[2])

    user_states[call.from_user.id] = {
        "step": "set_delete_time",
        "pair_index": index
    }

    await call.message.edit_text(
        "Send delete time in seconds\n\nExample:\n10 = delete after 10 sec\n0 = disable"
    )

# ================= BUTTON SYSTEM =================

async def build_buttons():

    db = await load_db()

    if not db["buttons"]:
        return None

    kb = InlineKeyboardBuilder()

    for b in db["buttons"]:
        kb.add(InlineKeyboardButton(text=b["text"], url=b["url"]))

    kb.adjust(1)

    return kb.as_markup()
    
    
    
    
@dp.message(Command("access"))
async def add_admin(message: Message):

    if message.from_user.id != OWNER_ID:
        await message.answer("❌ Only Owner Can Add Admin")
        return

    args = message.text.split()

    if len(args) != 2:
        await message.answer("Usage:\n/access USER_ID")
        return

    try:
        admin_id = int(args[1])
    except:
        await message.answer("Send Valid User ID")
        return

    db = await load_db()

    if admin_id in db["admins"]:
        await message.answer("⚠️ Already Admin")
        return

    db["admins"].append(admin_id)
    await save_db(db)

    await message.answer(f"✅ Admin Added:\n{admin_id}")
    
@dp.message(Command("remove_admin"))
async def remove_admin(message: Message):

    if message.from_user.id != OWNER_ID:
        await message.answer("❌ Only Owner Can Remove Admin")
        return

    args = message.text.split()

    if len(args) != 2:
        await message.answer("Usage:\n/remove_admin USER_ID")
        return

    try:
        admin_id = int(args[1])
    except:
        await message.answer("Send Valid User ID")
        return

    db = await load_db()

    if admin_id not in db["admins"]:
        await message.answer("❌ Not Admin")
        return

    db["admins"].remove(admin_id)
    await save_db(db)

    await message.answer(f"✅ Admin Removed:\n{admin_id}")
    
@dp.message(Command("admins"))
async def list_admins(message: Message):

    if message.from_user.id != OWNER_ID:
        return

    db = await load_db()

    text = "👑 <b>ADMIN PANEL</b>\n\n"

    # Admin List
    if not db["admins"]:
        text += "📭 No Admins Added\n\n"
    else:
        text += "📋 <b>Admin List:</b>\n"
        for a in db["admins"]:
            text += f"• <code>{a}</code>\n"
        text += "\n"

    # Commands Guide
    text += (
        "⚙ <b>Commands:</b>\n\n"
        "➕ Add Admin:\n"
        "<code>/access USER_ID</code>\n\n"

        "❌ Remove Admin:\n"
        "<code>/remove_admin USER_ID</code>\n\n"

        "👀 Show Admin List:\n"
        "<code>/admins</code>\n"
    )

    await message.answer(text, parse_mode="HTML")

# ================= FORWARD SYSTEM =================

@dp.message(F.chat.type.in_(["group", "supergroup"]))
async def forward_handler(message: Message):
    db = await load_db()

    if not db.get("global_enabled", True):
        return

    for pair in db.get("pairs", []):

        if not pair.get("enabled", True):
            continue

        if message.chat.id == pair["from"]:

            # 🔗 LINK FILTER
            text = message.text or message.caption

            if pair.get("link_filter"):
                if text and ("http" in text or "t.me" in text or "www." in text):
                    print("🔗 Link blocked")
                    continue

            try:

                sent = await bot.copy_message(
                    chat_id=pair["to"],
                    from_chat_id=message.chat.id,
                    message_id=message.message_id,
                    reply_markup=build_buttons()
                )

                print("✅ Forwarded with Buttons")

                # ⏱ AUTO DELETE
                delete_time = pair.get("delete_time", 0)

                if delete_time > 0:

                    await asyncio.sleep(delete_time)

                    try:
                        await bot.delete_message(pair["to"], sent.message_id)
                    except:
                        pass

            except Exception as e:
                print("❌ Error:", e)

# ================= MAIN =================

async def main():
    print("🚀 Bot Starting...")
    await start_web_server()   # Render port binding
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())