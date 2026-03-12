import asyncio
import os
import re
from aiohttp import web

from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon import Button
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from motor.motor_asyncio import AsyncIOMotorClient

# ================= ENV =================

TOKEN = os.getenv("TOKEN")
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
SESSION = os.getenv("SESSION")
MONGO_URI = os.getenv("MONGO_URI")

OWNER_ID = 6860983540

if not TOKEN:
    raise ValueError("TOKEN not found!")
if not API_ID:
    raise ValueError("API_ID not found!")
if not API_HASH:
    raise ValueError("API_HASH not found!")
if not SESSION:
    raise ValueError("SESSION not found!")
if not MONGO_URI:
    raise ValueError("MONGO_URI not found!")

API_ID = int(API_ID)
OTP_PATTERN = r"\d{3}[- ]?\d{3}"
# ================= CLIENTS =================



bot = Bot(token=TOKEN)
dp = Dispatcher()  # ✅ No argument here in v3


# Telethon userbot (Forwarding ke liye)
userbot = TelegramClient(
    StringSession(SESSION),
    API_ID,
    API_HASH
)



# ================= DATABASE =================

mongo_client = AsyncIOMotorClient(MONGO_URI)

db = mongo_client["forward_bot"]

config_collection = db["forward_config"]

user_states = {}


# ================= DATABASE FUNCTIONS =================

async def load_db():

    data = await config_collection.find_one({"_id": "main"})

    if not data:

        data = {
            "_id": "main",
            "admins": [],
            "pairs": [],
            "buttons": [],
            "filters": [],
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


# ================= WEB SERVER (RENDER KEEP ALIVE) =================

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


# ================= MENUS (BOT PANEL) =================

def main_menu():

    return InlineKeyboardMarkup(inline_keyboard=[

        [
            InlineKeyboardButton(text="➕ Add Pair", callback_data="add_pair"),
            InlineKeyboardButton(text="❌ Remove Pair", callback_data="remove_pair")
        ],

        [
            InlineKeyboardButton(text="🔁 Toggle Pair", callback_data="toggle_pair"),
            InlineKeyboardButton(text="✏ Rename Pair", callback_data="rename_pair")
        ],

        [
            InlineKeyboardButton(text="⏱ Auto Delete Time", callback_data="delete_time"),
            InlineKeyboardButton(text="🔗 Link Filter", callback_data="link_filter")
        ],
        
        [
            InlineKeyboardButton(text="🚫 Filter Manager", callback_data="filter_manager")
        ],
        
        [
    InlineKeyboardButton(text="✂️ Message Editor",  callback_data="msg_editor")
        ],

        [
    InlineKeyboardButton(text="🔑 OTP Reader", callback_data="otp_reader")
        ],
           
        [
            InlineKeyboardButton(text="📊 Status", callback_data="status"),
            InlineKeyboardButton(text="🌐 Global ON/OFF", callback_data="global")
        ],

        [
            InlineKeyboardButton(text="🔘 Button Manager", callback_data="button_manager"),
            InlineKeyboardButton(text="📝 Start Msg Manager", callback_data="start_manager")
        ]

    ])
    
def back_button():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Back", callback_data="back")]
        ]
    )


# ================= START =================

@dp.message(Command("start"))
async def start_cmd(message: types.Message):

    uid = message.from_user.id
    data = await load_db()

    try:
        admin = await is_admin(uid)
    except:
        admin = False

    if admin:
        await message.answer(
            "🚀 <b>FORWARD BOT CONTROL PANEL</b>\n\n"
            "Use <code>/panel</code> to open the control panel.",
            parse_mode="html"
        )
        return

    if data.get("start_message"):
        await message.answer(data["start_message"])
    else:
        await message.answer("👋 Welcome!")


# ================= PANEL (OWNER CONTROL) =================

@dp.message(Command("panel"))
async def panel_cmd(message: types.Message):

    if not await is_admin(message.from_user.id):
        return

    await message.answer(
        "🚀 <b>FORWARD BOT CONTROL PANEL</b>",
        reply_markup=main_menu(),
        parse_mode="html"
    )



@dp.message(Command("admin"))
async def admin_help(message: types.Message):

    if not await is_admin(message.from_user.id):
        return

    text = """
🛠 <b>BOT ADMIN FEATURES</b>

➕ <b>Add Pair</b>
Adds a forwarding pair from a source group to a destination chat.

❌ <b>Remove Pair</b>
Deletes an existing forwarding pair.

🔁 <b>Toggle Pair</b>
Enable or disable forwarding for a specific pair.

✏ <b>Rename Pair</b>
Set a custom name for a pair to identify it easily.

⏱ <b>Auto Delete Time</b>
Automatically delete forwarded messages after a set time.

🔗 <b>Link Filter</b>
Blocks messages containing links when enabled.

🚫 <b>Filter Manager</b>
Blocks messages containing specific words.

✂️ <b>Message Editor</b>
Allows removing unwanted words from forwarded messages.
Example: remove words like "Received" or "DEV".

🔑 <b>OTP Reader</b>
Reads OTP codes from inline buttons and forwards them
together with the message text.

📊 <b>Status</b>
Shows bot statistics and current system status.

🌐 <b>Global ON/OFF</b>
Enable or disable the entire forwarding system.

🔘 <b>Button Manager</b>
Add buttons under forwarded messages.

📝 <b>Start Message Manager</b>
Set or change the /start message for users.

👮 <b>Admin Commands</b>

<code>/access USER_ID</code>
Add a new admin.

<code>/remove_admin USER_ID</code>
Remove an admin.

<code>/admins</code>
View the list of admins.
"""

    await message.answer(text, parse_mode="html")
    
# ================= ADD PAIR =================

@dp.callback_query(lambda c: c.data == "add_pair")
async def add_pair_menu(callback: types.CallbackQuery):

    user_states[callback.from_user.id] = {"step": "add_pair_from"}

    await callback.message.edit_text(
        "📥 Send SOURCE Chat ID\n\nExample:\n<code>-1001234567890</code>",
        reply_markup=back_button(),
        parse_mode="html"
    )


# ================= REMOVE PAIR =================

@dp.callback_query(lambda c: c.data == "remove_pair")
async def remove_pair_menu(callback: types.CallbackQuery):

    data = await load_db()

    if not data["pairs"]:
        await callback.answer("❌ No pairs added", show_alert=True)
        return

    buttons = []

    for i, pair in enumerate(data["pairs"]):

        name = pair.get("name", f"{pair['from']} ➜ {pair['to']}")

        buttons.append(
            [InlineKeyboardButton(text=name, callback_data=f"delpair_{i}")]
        )

    buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data="back")])

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)

    await callback.message.edit_text(
        "❌ Select Pair to Remove",
        reply_markup=kb
    )


@dp.callback_query(lambda c: c.data.startswith("delpair_"))
async def remove_pair(callback: types.CallbackQuery):

    data = await load_db()

    index = int(callback.data.split("_")[1])

    if index >= len(data["pairs"]):
        await callback.answer("❌ Invalid Pair", show_alert=True)
        return

    data["pairs"].pop(index)

    await save_db(data)

    await callback.answer("✅ Pair Removed")

    await callback.message.edit_text(
        "✅ Pair Removed Successfully",
        reply_markup=main_menu()
    )


# ================= TOGGLE PAIR =================

@dp.callback_query(lambda c: c.data == "toggle_pair")
async def toggle_pair_menu(callback: types.CallbackQuery):

    data = await load_db()

    if not data["pairs"]:
        await callback.answer("❌ No pairs available", show_alert=True)
        return

    buttons = []

    for i, pair in enumerate(data["pairs"]):

        status = "🟢 ON" if pair.get("enabled", True) else "🔴 OFF"

        name = pair.get("name", f"{pair['from']} ➜ {pair['to']}")

        buttons.append(
            [InlineKeyboardButton(text=f"{name} ({status})", callback_data=f"toggle_{i}")]
        )

    buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data="back")])

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)

    await callback.message.edit_text(
        "🔁 Toggle Pair",
        reply_markup=kb
    )


@dp.callback_query(lambda c: c.data.startswith("toggle_"))
async def toggle_pair(callback: types.CallbackQuery):

    data = await load_db()

    index = int(callback.data.split("_")[1])

    if index >= len(data["pairs"]):
        await callback.answer("❌ Invalid Pair", show_alert=True)
        return

    data["pairs"][index]["enabled"] = not data["pairs"][index].get("enabled", True)

    await save_db(data)

    await callback.answer("✅ Updated")

    await toggle_pair_menu(callback)



# ================= OTP READER =================

@dp.callback_query(lambda c: c.data == "otp_reader")
async def otp_reader_menu(callback: types.CallbackQuery):

    data = await load_db()

    if not data["pairs"]:
        await callback.answer("❌ No pairs available", show_alert=True)
        return

    buttons = []

    for i, pair in enumerate(data["pairs"]):

        status = "🟢 ON" if pair.get("otp_reader", False) else "🔴 OFF"

        name = pair.get("name", f"{pair['from']} ➜ {pair['to']}")

        buttons.append(
            [InlineKeyboardButton(text=f"{name} ({status})", callback_data=f"otp_{i}")]
        )

    buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data="back")])

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)

    await callback.message.edit_text(
        "🔑 Select Pair to Toggle OTP Reader",
        reply_markup=kb
    )


@dp.callback_query(lambda c: c.data.startswith("otp_"))
async def toggle_otp_reader(callback: types.CallbackQuery):

    data = await load_db()

    index = int(callback.data.split("_")[1])

    if index >= len(data["pairs"]):
        await callback.answer("❌ Invalid Pair", show_alert=True)
        return

    pair = data["pairs"][index]

    pair["otp_reader"] = not pair.get("otp_reader", False)

    await save_db(data)

    await callback.answer("✅ OTP Reader Updated")

    await otp_reader_menu(callback)
    
# ================= STATUS =================

@dp.callback_query(lambda c: c.data == "status")
async def status_panel(callback: types.CallbackQuery):

    data = await load_db()

    pairs = data.get("pairs", [])
    buttons = data.get("buttons", [])
    admins = data.get("admins", [])

    total_pairs = len(pairs)
    active_pairs = len([p for p in pairs if p.get("enabled", True)])
    disabled_pairs = total_pairs - active_pairs

    total_filters = sum(len(p.get("filters", [])) for p in pairs)

    text = "📊 <b>BOT STATUS PANEL</b>\n\n"

    text += "🔁 <b>Pairs</b>\n"
    text += f"• Total : {total_pairs}\n"
    text += f"• Active : {active_pairs}\n"
    text += f"• Disabled : {disabled_pairs}\n\n"

    text += "🚫 <b>Filters</b>\n"
    text += f"• Total Filters : {total_filters}\n\n"

    text += "🔘 <b>Buttons</b>\n"
    text += f"• Total : {len(buttons)}\n\n"

    text += "👮 <b>Admins</b>\n"
    text += f"• Total : {len(admins)}\n\n"

    if data.get("global_enabled", True):
        text += "🌐 <b>Global Forward</b> : 🟢 ON"
    else:
        text += "🌐 <b>Global Forward</b> : 🔴 OFF"

    await callback.message.edit_text(
        text,
        reply_markup=back_button(),
        parse_mode="html"
    )


# ================= GLOBAL TOGGLE =================

@dp.callback_query(lambda c: c.data == "global")
async def global_toggle(callback: types.CallbackQuery):

    data = await load_db()

    data["global_enabled"] = not data.get("global_enabled", True)

    await save_db(data)

    if data["global_enabled"]:
        msg = "🌐 Global Forward 🟢 ON"
    else:
        msg = "🌐 Global Forward 🔴 OFF"

    await callback.answer(msg)

    await callback.message.edit_text(
        msg,
        reply_markup=main_menu()
    )





@dp.callback_query(lambda c: c.data == "back")
async def back(callback: types.CallbackQuery):

    await callback.message.edit_text(
        "🚀 <b>FORWARD BOT CONTROL PANEL</b>",
        reply_markup=main_menu(),
        parse_mode="html"
    )


# ================= START MESSAGE MANAGER =================

def start_menu():

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📝 Set Start Message", callback_data="set_start")],
            [InlineKeyboardButton(text="👀 View Start Message", callback_data="view_start")],
            [InlineKeyboardButton(text="❌ Remove Start Message", callback_data="remove_start")],
            [InlineKeyboardButton(text="🔙 Back", callback_data="back")]
        ]
    )

def filter_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Add Filter", callback_data="add_filter")],
            [InlineKeyboardButton(text="❌ Remove Filter", callback_data="remove_filter")],
            [InlineKeyboardButton(text="👀 View Filters", callback_data="view_filter")],
            [InlineKeyboardButton(text="🔙 Back", callback_data="back")]
        ]
    )




@dp.callback_query(lambda c: c.data == "start_manager")
async def start_manager(callback: types.CallbackQuery):

    await callback.message.edit_text(
        "📝 <b>START MESSAGE MANAGER</b>",
        reply_markup=start_menu(),
        parse_mode="html"
    )


@dp.callback_query(lambda c: c.data == "set_start")
async def set_start(callback: types.CallbackQuery):

    user_states[callback.from_user.id] = {"step": "set_start"}

    await callback.message.edit_text(
        "📨 Send new Start Message:",
        reply_markup=back_button()
    )


@dp.callback_query(lambda c: c.data == "filter_manager")
async def filter_manager(callback: types.CallbackQuery):

    await callback.message.edit_text(
        "🚫 <b>FILTER MANAGER</b>",
        reply_markup=filter_menu(),
        parse_mode="html"
    )
    


@dp.callback_query(lambda c: c.data == "msg_editor")
async def msg_editor(callback: types.CallbackQuery):

    buttons = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Add Editor", callback_data="add_editor")],
            [InlineKeyboardButton(text="👀 View Editors", callback_data="view_editor")],
            [InlineKeyboardButton(text="❌ Remove Editor", callback_data="remove_editor")],
            [InlineKeyboardButton(text="🔙 Back", callback_data="back")]
        ]
    )

    await callback.message.edit_text(
        "✂️ <b>MESSAGE EDITOR PANEL</b>",
        reply_markup=buttons,
        parse_mode="html"
    )
    
    
@dp.callback_query(lambda c: c.data == "add_editor")
async def add_editor(callback: types.CallbackQuery):

    db = await load_db()

    if not db["pairs"]:
        await callback.answer("No pairs added", show_alert=True)
        return

    buttons = []

    for i, pair in enumerate(db["pairs"]):

        name = pair.get("name", f"{pair['from']} ➜ {pair['to']}")

        buttons.append(
            [InlineKeyboardButton(text=name, callback_data=f"editmsg_{i}")]
        )

    buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data="msg_editor")])

    await callback.message.edit_text(
        "✂️ Select Pair for Message Editor",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )
    
    
@dp.callback_query(lambda c: c.data == "view_editor")
async def view_editor(callback: types.CallbackQuery):

    db = await load_db()

    text = "✂️ <b>MESSAGE EDITORS</b>\n\n"

    for pair in db["pairs"]:

        name = pair.get("name", f"{pair['from']} ➜ {pair['to']}")

        keywords = pair.get("keyword_filters", [])
        removes = pair.get("remove_words", [])

        text += f"<b>{name}</b>\n"

        if keywords:
            for k, r in zip(keywords, removes):
                text += f"Keyword : {k}\n"
                text += f"Remove  : {r}\n\n"
        else:
            text += "No Editor\n\n"

    await callback.message.edit_text(
        text,
        parse_mode="html",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Back", callback_data="msg_editor")]
            ]
        )
    )
    
@dp.callback_query(lambda c: c.data == "remove_editor")
async def remove_editor(callback: types.CallbackQuery):

    db = await load_db()

    buttons = []

    for i, pair in enumerate(db["pairs"]):

        if pair.get("keyword_filters"):

            name = pair.get("name", f"{pair['from']} ➜ {pair['to']}")

            buttons.append(
                [InlineKeyboardButton(text=name, callback_data=f"del_editor_{i}")]
            )

    if not buttons:
        await callback.answer("❌ No Editors Found", show_alert=True)
        return

    buttons.append(
        [InlineKeyboardButton(text="🔙 Back", callback_data="msg_editor")]
    )

    await callback.message.edit_text(
        "❌ Select Pair to Remove Editor",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )
    
    
@dp.callback_query(lambda c: c.data.startswith("del_editor_"))
async def delete_editor(callback: types.CallbackQuery):

    db = await load_db()

    index = int(callback.data.split("_")[2])

    if index >= len(db["pairs"]):
        await callback.answer("Invalid Pair", show_alert=True)
        return

    db["pairs"][index]["keyword_filters"] = []
    db["pairs"][index]["remove_words"] = []

    await save_db(db)

    await callback.answer("✅ Editor Removed")

    await msg_editor(callback)
    
@dp.callback_query(lambda c: c.data == "add_filter")
async def add_filter_menu(callback: types.CallbackQuery):

    db = await load_db()

    if not db["pairs"]:
        await callback.answer("No pairs added", show_alert=True)
        return

    buttons = []

    for i, pair in enumerate(db["pairs"]):

        name = pair.get("name", f"{pair['from']} ➜ {pair['to']}")

        buttons.append(
            [InlineKeyboardButton(text=name, callback_data=f"addfilter_{i}")]
        )

    buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data="filter_manager")])

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)

    await callback.message.edit_text(
        "Select pair to add filter",
        reply_markup=kb
    )



@dp.callback_query(lambda c: c.data.startswith("editmsg_"))
async def editmsg(callback: types.CallbackQuery):

    index = int(callback.data.split("_")[1])

    user_states[callback.from_user.id] = {
        "step": "set_keyword",
        "pair_index": index
    }

    await callback.message.edit_text(
        "🔎 Send keyword to match message",
        reply_markup=back_button(),
        parse_mode="html"
    )    
    


@dp.callback_query(lambda c: c.data.startswith("addfilter_"))
async def add_filter_select(callback: types.CallbackQuery):

    index = int(callback.data.split("_")[1])

    user_states[callback.from_user.id] = {
        "step": "add_filter_word",
        "pair_index": index
    }

    await callback.message.edit_text(
        "✏ Send word to block"
    )
    
    
@dp.callback_query(lambda c: c.data == "view_filter")
async def view_filter_menu(callback: types.CallbackQuery):

    db = await load_db()

    if not db["pairs"]:
        await callback.answer("No pairs", show_alert=True)
        return

    text = "🚫 <b>PAIR FILTERS</b>\n\n"

    for pair in db["pairs"]:

        name = pair.get("name", f"{pair['from']} ➜ {pair['to']}")

        filters = pair.get("filters", [])

        text += f"<b>{name}</b>\n"

        if not filters:
            text += "No filters\n\n"
        else:
            for f in filters:
                text += f"• {f}\n"

            text += "\n"

    await callback.message.edit_text(
        text,
        reply_markup=filter_menu(),
        parse_mode="html"
    )
    
@dp.callback_query(lambda c: c.data == "remove_filter")
async def remove_filter_menu(callback: types.CallbackQuery):

    db = await load_db()

    buttons = []

    for i, pair in enumerate(db["pairs"]):

        name = pair.get("name", f"{pair['from']} ➜ {pair['to']}")

        buttons.append(
            [InlineKeyboardButton(text=name, callback_data=f"delfilter_{i}")]
        )

    buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data="filter_manager")])

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)

    await callback.message.edit_text(
        "Select pair to remove filter",
        reply_markup=kb
    )
    
@dp.callback_query(lambda c: c.data.startswith("delfilter_"))
async def delete_filter(callback: types.CallbackQuery):

    db = await load_db()

    index = int(callback.data.split("_")[1])

    if index >= len(db["pairs"]):
        await callback.answer("Invalid pair", show_alert=True)
        return

    db["pairs"][index]["filters"] = []

    await save_db(db)

    await callback.answer("Filters cleared")

    await filter_manager(callback)

# ================= RENAME PAIR =================

@dp.callback_query(lambda c: c.data == "rename_pair")
async def rename_pair_menu(callback: types.CallbackQuery):

    data = await load_db()

    if not data["pairs"]:
        await callback.answer("❌ No pairs available", show_alert=True)
        return

    buttons = []

    for i, pair in enumerate(data["pairs"]):

        name = pair.get("name", f"{pair['from']} ➜ {pair['to']}")

        buttons.append(
            [InlineKeyboardButton(text=name, callback_data=f"rename_{i}")]
        )

    buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data="back")])

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)

    await callback.message.edit_text(
        "✏ Select Pair to Rename",
        reply_markup=kb
    )


@dp.callback_query(lambda c: c.data.startswith("rename_"))
async def rename_select(callback: types.CallbackQuery):

    data = await load_db()

    index = int(callback.data.split("_")[1])

    if index >= len(data["pairs"]):
        await callback.answer("❌ Invalid Pair", show_alert=True)
        return

    user_states[callback.from_user.id] = {
        "step": "rename_pair",
        "pair_index": index
    }

    await callback.message.edit_text(
        "✏ Send new name for this pair:"
    )


# ================= BUTTON MANAGER =================

def button_menu():

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Add Button", callback_data="add_button")],
            [InlineKeyboardButton(text="❌ Remove Button", callback_data="remove_button")],
            [InlineKeyboardButton(text="👀 View Buttons", callback_data="view_buttons")],
            [InlineKeyboardButton(text="🔙 Back", callback_data="back")]
        ]
    )


@dp.callback_query(lambda c: c.data == "button_manager")
async def button_manager(callback: types.CallbackQuery):

    await callback.message.edit_text(
        "🔘 <b>BUTTON MANAGER</b>",
        reply_markup=button_menu(),
        parse_mode="html"
    )


@dp.callback_query(lambda c: c.data == "add_button")
async def add_button(callback: types.CallbackQuery):

    user_states[callback.from_user.id] = {"step": "add_button_text"}

    await callback.message.edit_text(
        "📝 Send Button Text:"
    )


# ================= REMOVE BUTTON =================

@dp.callback_query(lambda c: c.data == "remove_button")
async def remove_button_menu(callback: types.CallbackQuery):

    data = await load_db()

    if not data["buttons"]:
        await callback.answer("❌ No buttons available", show_alert=True)
        return

    buttons = []

    for i, b in enumerate(data["buttons"]):

        buttons.append(
            [InlineKeyboardButton(text=b["text"], callback_data=f"delbtn_{i}")]
        )

    buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data="back")])

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)

    await callback.message.edit_text(
        "❌ Select Button to Remove",
        reply_markup=kb
    )


@dp.callback_query(lambda c: c.data.startswith("delbtn_"))
async def remove_button(callback: types.CallbackQuery):

    data = await load_db()

    index = int(callback.data.split("_")[1])

    if index >= len(data["buttons"]):
        await callback.answer("❌ Invalid Button", show_alert=True)
        return

    data["buttons"].pop(index)

    await save_db(data)

    await callback.answer("✅ Button Removed")

    await callback.message.edit_text(
        "✅ Button Removed Successfully",
        reply_markup=button_menu()
    )


# ================= VIEW BUTTONS =================

@dp.callback_query(lambda c: c.data == "view_buttons")
async def view_buttons(callback: types.CallbackQuery):

    data = await load_db()

    if not data["buttons"]:

        await callback.message.edit_text(
            "❌ No Buttons Added",
            reply_markup=button_menu()
        )
        return

    text = "🔘 <b>Buttons List</b>\n\n"

    for b in data["buttons"]:
        text += f"• {b['text']} → {b['url']}\n"

    await callback.message.edit_text(
        text,
        reply_markup=button_menu(),
        parse_mode="html"
    )


# ================= PRIVATE HANDLER =================

@dp.message()
async def private_handler(message: types.Message):

    uid = message.from_user.id

    if uid not in user_states:
        return

    state = user_states[uid]

    data = await load_db()

    text = message.text


    # ================= ADD BUTTON =================

    if state.get("step") == "add_button_text":

        user_states[uid]["step"] = "add_button_url"
        user_states[uid]["text"] = text

        await message.answer("🔗 Now send Button URL")

        return


    if state.get("step") == "add_button_url":

        btn_text = state["text"]
        url = text

        data["buttons"].append({
            "text": btn_text,
            "url": url
        })

        await save_db(data)

        user_states.pop(uid)

        await message.answer(
            "✅ Button Added Successfully",
            reply_markup=button_menu()
        )

        return


    # ================= ADD PAIR =================

    if state.get("step") == "add_pair_from":

        try:
            chat_from = int(text)
        except:
            await message.answer("❌ Send valid SOURCE Chat ID")
            return

        user_states[uid]["step"] = "add_pair_to"
        user_states[uid]["from"] = chat_from

        await message.answer("📥 Now send DESTINATION Chat ID")

        return


    if state.get("step") == "add_pair_to":

        try:
            chat_to = int(text)
        except:
            await message.answer("❌ Send valid DESTINATION Chat ID")
            return

        chat_from = state["from"]

        data["pairs"].append({
            "from": chat_from,
            "to": chat_to,
            "enabled": True,
            "delete_time": 0,
            "link_filter": False,
            "filters": [],
            "keyword_filters": [],
            "remove_words": [],
            "otp_reader": True
        })
    
        await save_db(data)

        user_states.pop(uid)

        await message.answer(
            "✅ Pair Added Successfully",
            reply_markup=main_menu()
        )
    
        return


    # ================= RENAME PAIR =================

    if state.get("step") == "rename_pair":

        index = state["pair_index"]

        if index >= len(data["pairs"]):
            await message.answer("❌ Invalid Pair")
            user_states.pop(uid)
            return

        data["pairs"][index]["name"] = text

        await save_db(data)

        user_states.pop(uid)

        await message.answer(
            "✅ Pair Renamed Successfully",
            reply_markup=main_menu()
        )

        return


    # ================= SET START MESSAGE =================

    if state.get("step") == "set_start":

        data["start_message"] = text

        await save_db(data)

        user_states.pop(uid)

        await message.answer(
            "✅ Start Message Updated",
            reply_markup=main_menu()
        )

        return
        
        
# ================= ADD FILTER =================

    if state.get("step") == "add_filter_word":

        index = state["pair_index"]

        word = text.lower()

        if index >= len(data["pairs"]):
            await message.answer("❌ Invalid Pair")
            user_states.pop(uid)
            return

        data["pairs"][index].setdefault("filters", [])

        data["pairs"][index]["filters"].append(word)

        await save_db(data)

        user_states.pop(uid)

        await message.answer(
            f"✅ Filter added:\n<code>{word}</code>",
            reply_markup=filter_menu(),
            parse_mode="html"
        )

        return


    # ================= SET DELETE TIME =================

    if state.get("step") == "set_delete_time":

        try:
            t = int(text)
        except ValueError:
            await message.answer("❌ Send a valid number only")
            return

        index = state["pair_index"]

        if index >= len(data["pairs"]):
            await message.answer("❌ Invalid Pair")
            user_states.pop(uid)
            return

        data["pairs"][index]["delete_time"] = t

        await save_db(data)

        user_states.pop(uid)

        msg = "❌ Auto Delete Disabled" if t == 0 else f"✅ Auto Delete Set\n⏱ Time: {t}s"

        await message.answer(
            msg,
            reply_markup=main_menu()
        )

        return
        
        
        
        # SET KEYWORD
    # SET KEYWORD
    if state.get("step") == "set_keyword":

        index = state["pair_index"]

        data["pairs"][index].setdefault("keyword_filters", [])
 
        data["pairs"][index]["keyword_filters"].append(text)

        await save_db(data)

        user_states[uid]["step"] = "set_remove"
    
        await message.answer(
            "✂️ Send word to remove",
            reply_markup=back_button()
        )

        return
        
        
        
    # SET REMOVE WORD
    # SET REMOVE WORD
    if state.get("step") == "set_remove":

        index = state["pair_index"]
  
        data["pairs"][index].setdefault("remove_words", [])

        data["pairs"][index]["remove_words"].append(text)

        await save_db(data)
 
        user_states.pop(uid)

        await message.answer(
            "✅ Message Editor Saved",
            reply_markup=main_menu()
        )
  
        return
        
        
        
        
        
@dp.callback_query(lambda c: c.data == "view_start")
async def view_start(callback: types.CallbackQuery):

    db = await load_db()

    if db.get("start_message"):
        text = f"📢 <b>Current Start Message</b>\n\n{db['start_message']}"
    else:
        text = "❌ No Start Message Set."

    await callback.message.edit_text(
        text,
        reply_markup=start_menu(),
        parse_mode="html"
    )
    
    
    
@dp.callback_query(lambda c: c.data == "remove_start")
async def remove_start(callback: types.CallbackQuery):

    db = await load_db()

    db["start_message"] = None

    await save_db(db)

    await callback.answer("Removed ✅")

    await start_manager(callback)
    

@dp.callback_query(lambda c: c.data == "link_filter")
async def link_filter_menu(callback: types.CallbackQuery):

    db = await load_db()

    if not db.get("pairs"):
        await callback.answer("No pairs added", show_alert=True)
        return

    buttons = []

    for i, pair in enumerate(db["pairs"]):

        status = "ON" if pair.get("link_filter", False) else "OFF"

        name = pair.get("name", f"{pair['from']} ➜ {pair['to']}")

        buttons.append([
            InlineKeyboardButton(text=f"{name} ({status})", callback_data=f"link_{i}")
        ])

    buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data="back")])

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)

    await callback.message.edit_text(
        "🔗 Toggle Link Filter",
        reply_markup=kb
    )
    
@dp.callback_query(lambda c: c.data.startswith("link_"))
async def link_toggle(callback: types.CallbackQuery):

    db = await load_db()

    index = int(callback.data.split("_")[1])

    if index >= len(db.get("pairs", [])):
        await callback.answer("Invalid Pair", show_alert=True)
        return

    current = db["pairs"][index].get("link_filter", False)

    db["pairs"][index]["link_filter"] = not current

    await save_db(db)

    await callback.answer("Updated ✅")

    await link_filter_menu(callback)
    
@dp.callback_query(lambda c: c.data == "delete_time")
async def delete_time_menu(callback: types.CallbackQuery):

    db = await load_db()

    if not db.get("pairs"):
        await callback.answer("No pairs added", show_alert=True)
        return

    buttons = []

    for i, pair in enumerate(db["pairs"]):

        t = pair.get("delete_time", 0)

        status = "OFF" if t == 0 else f"{t}s"

        name = pair.get("name", f"{pair['from']} ➜ {pair['to']}")

        buttons.append([
            InlineKeyboardButton(
                text=f"{name} ({status})",
                callback_data=f"set_dtime_{i}"
            )
        ])

    buttons.append([
        InlineKeyboardButton(text="🔙 Back", callback_data="back")
    ])

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)

    await callback.message.edit_text(
        "⏱ Select Pair to Set Delete Time",
        reply_markup=kb
    )


# ================= ASK DELETE TIME =================

@dp.callback_query(lambda c: c.data.startswith("set_dtime_"))
async def ask_delete_time(callback: types.CallbackQuery):

    db = await load_db()

    try:
        index = int(callback.data.split("_")[2])
    except:
        await callback.answer("❌ Invalid Data", show_alert=True)
        return

    if index >= len(db.get("pairs", [])):
        await callback.answer("❌ Invalid Pair", show_alert=True)
        return

    user_states[callback.from_user.id] = {
        "step": "set_delete_time",
        "pair_index": index
    }

    await callback.message.edit_text(
        "⏱ <b>Send delete time in seconds</b>\n\n"
        "Example:\n"
        "10 = delete after 10 sec\n"
        "0 = disable",
        parse_mode="html"
    )


# ================= BUTTON SYSTEM =================

async def build_buttons():

    db = await load_db()

    if not db.get("buttons"):
        return None

    buttons = []

    for b in db["buttons"]:
        buttons.append(
            [InlineKeyboardButton(text=b["text"], url=b["url"])]
        )

    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ================= BUTTON MENU =================


# ================= ADMIN COMMANDS =================

@dp.message(lambda m: m.text and m.text.startswith("/access"))
async def add_admin(message: types.Message):

    if message.chat.type != "private":
        return

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
        await message.answer("❌ Send Valid User ID")
        return

    db = await load_db()
    db.setdefault("admins", [])

    if admin_id in db["admins"]:
        await message.answer("⚠️ Already Admin")
        return

    db["admins"].append(admin_id)
    await save_db(db)

    await message.answer(
        f"✅ <b>Admin Added</b>\n\n<code>{admin_id}</code>",
        parse_mode="html"
    )


@dp.message(lambda m: m.text and m.text.startswith("/remove_admin"))
async def remove_admin(message: types.Message):

    if message.chat.type != "private":
        return

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
        await message.answer("❌ Send Valid User ID")
        return

    db = await load_db()
    db.setdefault("admins", [])

    if admin_id not in db["admins"]:
        await message.answer("❌ Not Admin")
        return

    db["admins"].remove(admin_id)
    await save_db(db)

    await message.answer(
        f"✅ <b>Admin Removed</b>\n\n<code>{admin_id}</code>",
        parse_mode="html"
    )


@dp.message(lambda m: m.text == "/admins")
async def list_admins(message: types.Message):

    if message.chat.type != "private":
        return

    if message.from_user.id != OWNER_ID:
        return

    db = await load_db()
    db.setdefault("admins", [])

    text = "👑 <b>ADMIN PANEL</b>\n\n"

    if not db["admins"]:
        text += "📭 No Admins Added\n\n"
    else:
        text += "📋 <b>Admin List:</b>\n"
        for a in db["admins"]:
            text += f"• <code>{a}</code>\n"
        text += "\n"

    text += (
        "⚙ <b>Commands:</b>\n\n"
        "➕ Add Admin:\n"
        "<code>/access USER_ID</code>\n\n"
        "❌ Remove Admin:\n"
        "<code>/remove_admin USER_ID</code>\n\n"
        "👀 Show Admin List:\n"
        "<code>/admins</code>"
    )

    await message.answer(text, parse_mode="html")


# ================= FORWARD SYSTEM =================

@userbot.on(events.NewMessage(incoming=True))
@userbot.on(events.MessageEdited(incoming=True))
async def forward_handler(event):

    if event.is_private:
        return

    db = await load_db()

    if not db.get("global_enabled", True):
        return

    text = event.message.message or ""

    for pair in db.get("pairs", []):

        if not pair.get("enabled", True):
            continue

        if abs(event.chat_id) != abs(pair["from"]):
            continue

        # ================= KEYWORD FILTER (MULTIPLE) =================

        keywords = pair.get("keyword_filters", [])
        remove_words = pair.get("remove_words", [])

        if keywords:
            matched = False

            for k in keywords:
                if k.lower() in text.lower():
                    matched = True
                    break

            if not matched:
                continue

        # ================= REMOVE WORDS =================

        for rw in remove_words:
            text = text.replace(rw, "")

        # ================= LINK FILTER =================

        if pair.get("link_filter"):
            if any(x in text.lower() for x in ["http", "https", "t.me", "www."]):
                print("🔗 Link blocked")
                continue

        # ================= WORD FILTER =================

        filters = pair.get("filters", [])

        blocked = False
        for word in filters:
            if word.lower() in text.lower():
                print(f"🚫 Pair filter blocked: {word}")
                blocked = True
                break

        if blocked:
            continue

        asyncio.create_task(process_forward(event, pair, text))


async def process_forward(event, pair, text):

    try:

        file = None

        if event.message.media:
            file = await event.message.download_media()

        # ================= OTP FORMAT CLEANER =================

        if pair.get("otp_reader", True):

            import re
            otp_line = None

            # 1️⃣ Check OTP in text first
            otp_match = re.search(r"\b\d{3}[- ]?\d{3}\b", text)

            if otp_match:
                otp_line = f"Otp - {otp_match.group()}"

            # 2️⃣ If not in text then check buttons
            if not otp_line and event.message.buttons:

                for row in event.message.buttons:
                    for btn in row:

                        btn_text = btn.text.strip()

                        otp_match = re.search(r"\b\d{3}[- ]?\d{3}\b", btn_text)

                        if otp_match:
                            otp_line = f"Otp - {otp_match.group()}"
                            break

                    if otp_line:
                        break

            # 3️⃣ Add OTP to message
            if otp_line:
                text = f"{text}\n\n{otp_line}"

        # ================= BUTTONS =================

        buttons = await build_buttons()

        # ================= SEND MESSAGE =================

        if file:
            msg = await bot.send_document(
                pair["to"],
                file,
                caption=text if text else "",
                reply_markup=buttons
            )
        else:
            msg = await bot.send_message(
                pair["to"],
                text if text else "",
                reply_markup=buttons
            )

        print("✅ Bot sent message")

        # ================= AUTO DELETE =================

        delete_time = pair.get("delete_time", 0)

        if delete_time > 0:
            asyncio.create_task(
                auto_delete(pair["to"], msg.message_id, delete_time)
            )

    except Exception as e:
        print("❌ Forward Error:", e)


async def auto_delete(chat_id, msg_id, delay):

    await asyncio.sleep(delay)

    try:
        await bot.delete_message(chat_id, msg_id)
        print("🗑 Message Deleted")

    except Exception as e:
        print("Delete Error:", e)

# ================= MAIN =================


import asyncio

async def main():
    print("🚀 Starting System...")

    asyncio.create_task(start_web_server())

    await userbot.start()
    print("✅ Userbot Connected")

    # FIX
    await bot.delete_webhook(drop_pending_updates=True)

    asyncio.create_task(dp.start_polling(bot))
    print("✅ Aiogram Bot Connected")

    await userbot.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())