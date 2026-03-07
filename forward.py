import asyncio
import os
from aiohttp import web

from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession

from aiogram import Bot, Dispatcher, types

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



# ================= CLIENTS =================

bot = Bot(token=TOKEN)

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

# ================= MENUS =================

def main_menu():

    return [
        [
            Button.inline("➕ Add Pair", b"add_pair"),
            Button.inline("❌ Remove Pair", b"remove_pair")
        ],
        [
            Button.inline("🔁 Toggle Pair", b"toggle_pair"),
            Button.inline("✏ Rename Pair", b"rename_pair")
        ],
        [
            Button.inline("⏱ Auto Delete Time", b"delete_time"),
            Button.inline("🔗 Link Filter", b"link_filter")
        ],
        [
            Button.inline("📊 Status", b"status"),
            Button.inline("🌐 Global ON/OFF", b"global")
        ],
        [
            Button.inline("🔘 Button Manager", b"button_manager"),
            Button.inline("📝 Start Msg Manager", b"start_manager")
        ]
    ]


def back_button():

    return [
        [Button.inline("🔙 Back", b"back")]
    ]
# ================= START =================

# ================= START =================

from aiogram import Dispatcher, types

dp = Dispatcher()

@dp.message(commands=["start"])
async def start_cmd(message: types.Message):

    uid = message.from_user.id
    data = await load_db()

    if await is_admin(uid):
        await message.answer(
            "🚀 <b>FORWARD BOT CONTROL PANEL</b>",
            parse_mode="html"
        )
        return

    if data.get("start_message"):
        await message.answer(data["start_message"])
    else:
        await message.answer("👋 Welcome!")


# ================= ADD PAIR =================

@userbot.on(events.CallbackQuery(data=b"add_pair"))
async def add_pair_menu(event):

    user_states[event.sender_id] = {"step": "add_pair_from"}

    await event.edit(
        "Send SOURCE Chat ID\n\nExample:\n-1001234567890",
        buttons=back_button()
    )


# ================= REMOVE PAIR =================

@userbot.on(events.CallbackQuery(data=b"remove_pair"))
async def remove_pair_menu(event):

    db = await load_db()

    if not db["pairs"]:
        await event.answer("No pairs added", alert=True)
        return

    buttons = []

    for i, pair in enumerate(db["pairs"]):

        name = pair.get("name", f"{pair['from']} ➜ {pair['to']}")

        buttons.append(
            [Button.inline(name, f"delpair_{i}".encode())]
        )

    buttons.append([Button.inline("🔙 Back", b"back")])

    await event.edit(
        "❌ Select Pair to Remove",
        buttons=buttons
    )


@userbot.on(events.CallbackQuery(pattern=b"delpair_"))
async def remove_pair(event):

    db = await load_db()

    index = int(event.data.decode().split("_")[1])

    db["pairs"].pop(index)

    await save_db(db)

    await event.answer("Pair Removed ✅")

    await event.edit(
        "Removed Successfully",
        buttons=main_menu()
    )


# ================= TOGGLE PAIR =================

@userbot.on(events.CallbackQuery(data=b"toggle_pair"))
async def toggle_pair_menu(event):

    db = await load_db()

    buttons = []

    for i, pair in enumerate(db["pairs"]):

        status = "ON" if pair.get("enabled", True) else "OFF"

        name = pair.get("name", f"{pair['from']} ➜ {pair['to']}")

        buttons.append(
            [Button.inline(f"{name} ({status})", f"toggle_{i}".encode())]
        )

    buttons.append([Button.inline("🔙 Back", b"back")])

    await event.edit(
        "🔁 Toggle Pair",
        buttons=buttons
    )


@userbot.on(events.CallbackQuery(pattern=b"toggle_"))
async def toggle_pair(event):

    db = await load_db()

    index = int(event.data.decode().split("_")[1])

    db["pairs"][index]["enabled"] = not db["pairs"][index].get("enabled", True)

    await save_db(db)

    await event.answer("Updated")

    await toggle_pair_menu(event)


# ================= STATUS =================

@userbot.on(events.CallbackQuery(data=b"status"))
async def status_panel(event):

    db = await load_db()

    text = "📊 BOT STATUS\n\n"

    text += f"Pairs : {len(db['pairs'])}\n"
    text += f"Buttons : {len(db['buttons'])}\n"
    text += f"Admins : {len(db['admins'])}\n"

    if db.get("global_enabled", True):
        text += "Global : ON"
    else:
        text += "Global : OFF"

    await event.edit(
        text,
        buttons=back_button()
    )


# ================= GLOBAL TOGGLE =================

@userbot.on(events.CallbackQuery(data=b"global"))
async def global_toggle(event):

    db = await load_db()

    db["global_enabled"] = not db.get("global_enabled", True)

    await save_db(db)

    if db["global_enabled"]:
        msg = "🌐 Global Forward ON"
    else:
        msg = "🌐 Global Forward OFF"

    await event.answer(msg)

    await event.edit(
        msg,
        buttons=main_menu()
    )
    


# ================= BACK BUTTON =================

@userbot.on(events.CallbackQuery(data=b"back"))
async def back(event):

    await event.edit(
        "🚀 <b>FORWARD BOT CONTROL PANEL</b>",
        buttons=main_menu(),
        parse_mode="html"
    )


# ================= START MESSAGE MANAGER =================

def start_menu():

    return [
        [Button.inline("📝 Set Start Message", b"set_start")],
        [Button.inline("👀 View Start Message", b"view_start")],
        [Button.inline("❌ Remove Start Message", b"remove_start")],
        [Button.inline("🔙 Back", b"back")]
    ]


@userbot.on(events.CallbackQuery(data=b"start_manager"))
async def start_manager(event):

    await event.edit(
        "📝 <b>START MESSAGE MANAGER</b>",
        buttons=start_menu(),
        parse_mode="html"
    )


@userbot.on(events.CallbackQuery(data=b"set_start"))
async def set_start(event):

    user_states[event.sender_id] = {"step": "set_start"}

    await event.edit(
        "Send new Start Message:",
        buttons=back_button()
    )


# ================= RENAME PAIR =================

@userbot.on(events.CallbackQuery(data=b"rename_pair"))
async def rename_pair_menu(event):

    db = await load_db()

    buttons = []

    for i, pair in enumerate(db["pairs"]):

        name = pair.get("name", f"{pair['from']} ➜ {pair['to']}")

        buttons.append(
            [Button.inline(name, f"rename_{i}".encode())]
        )

    buttons.append([Button.inline("🔙 Back", b"back")])

    await event.edit(
        "Select pair to rename",
        buttons=buttons
    )


@userbot.on(events.CallbackQuery(pattern=b"rename_"))
async def rename_select(event):

    index = int(event.data.decode().split("_")[1])

    user_states[event.sender_id] = {
        "step": "rename_pair",
        "pair_index": index
    }

    await event.edit("Send new name")


# ================= BUTTON MANAGER =================

@userbot.on(events.CallbackQuery(data=b"button_manager"))
async def button_manager(event):

    await event.edit(
        "🔘 BUTTON MANAGER",
        buttons=button_menu()
    )


@userbot.on(events.CallbackQuery(data=b"add_button"))
async def add_button(event):

    user_states[event.sender_id] = {"step": "add_button_text"}

    await event.edit("Send Button Text")


# ================= REMOVE BUTTON =================

@userbot.on(events.CallbackQuery(data=b"remove_button"))
async def remove_button_menu(event):

    db = await load_db()

    if not db["buttons"]:
        await event.answer("No buttons", alert=True)
        return

    buttons = []

    for i, b in enumerate(db["buttons"]):

        buttons.append(
            [Button.inline(b["text"], f"delbtn_{i}".encode())]
        )

    buttons.append([Button.inline("🔙 Back", b"back")])

    await event.edit(
        "Select button to remove",
        buttons=buttons
    )


@userbot.on(events.CallbackQuery(pattern=b"delbtn_"))
async def remove_button(event):

    db = await load_db()

    index = int(event.data.decode().split("_")[1])

    db["buttons"].pop(index)

    await save_db(db)

    await event.answer("Button Removed")

    await event.edit(
        "Removed Successfully",
        buttons=button_menu()
    )


# ================= VIEW BUTTONS =================

@userbot.on(events.CallbackQuery(data=b"view_buttons"))
async def view_buttons(event):

    db = await load_db()

    if not db["buttons"]:

        await event.edit(
            "No Buttons Added",
            buttons=button_menu()
        )
        return

    text = "🔘 Buttons List\n\n"

    for b in db["buttons"]:
        text += f"{b['text']} -> {b['url']}\n"

    await event.edit(
        text,
        buttons=button_menu()
    )



# ================= PRIVATE HANDLER =================

@userbot.on(events.NewMessage(func=lambda e: e.is_private))
async def private_handler(event):

    uid = event.sender_id

    if uid not in user_states:
        return

    state = user_states[uid]
    db = await load_db()

    text = event.raw_text


    # ================== ADD BUTTON ==================
    if state.get("step") == "add_button_text":

        user_states[uid]["step"] = "add_button_url"
        user_states[uid]["text"] = text

        await event.respond("📌 Now send Button URL")
        return


    if state.get("step") == "add_button_url":

        btn_text = state["text"]
        url = text

        db["buttons"].append({
            "text": btn_text,
            "url": url
        })

        await save_db(db)

        user_states.pop(uid)

        await event.respond(
            "✅ Button Added",
            buttons=button_menu()
        )
        return


    # ================== ADD PAIR ==================

    if state.get("step") == "add_pair_from":

        try:
            chat_from = int(text)
        except:
            await event.respond("❌ Send valid Chat ID")
            return

        user_states[uid]["step"] = "add_pair_to"
        user_states[uid]["from"] = chat_from

        await event.respond("Now send DESTINATION Chat ID")
        return


    if state.get("step") == "add_pair_to":

        try:
            chat_to = int(text)
        except:
            await event.respond("❌ Send valid Chat ID")
            return

        chat_from = state["from"]

        db["pairs"].append({
            "from": chat_from,
            "to": chat_to,
            "enabled": True,
            "delete_time": 0,
            "link_filter": False
        })

        await save_db(db)

        user_states.pop(uid)

        await event.respond(
            "✅ Pair Added Successfully",
            buttons=main_menu()
        )
        return


    # ================== RENAME PAIR ==================

    if state.get("step") == "rename_pair":

        index = state["pair_index"]

        db["pairs"][index]["name"] = text

        await save_db(db)

        user_states.pop(uid)

        await event.respond(
            "✅ Pair Renamed",
            buttons=main_menu()
        )
        return


    # ================== SET START MESSAGE ==================

    if state.get("step") == "set_start":

        db["start_message"] = text

        await save_db(db)

        user_states.pop(uid)

        await event.respond(
            "✅ Start Message Updated",
            buttons=main_menu()
        )
        return


    # ================== SET DELETE TIME ==================

    if state.get("step") == "set_delete_time":

        try:
            t = int(text)
        except ValueError:
            await event.respond("❌ Send a valid number only")
            return

        index = state["pair_index"]

        db["pairs"][index]["delete_time"] = t

        await save_db(db)

        user_states.pop(uid)

        msg = "❌ Auto Delete Disabled" if t == 0 else f"✅ Auto Delete Set Successfully\n⏱ Time: {t}s"

        await event.respond(
            msg,
            buttons=main_menu()
        )
        return


# ================= VIEW START MESSAGE =================

@userbot.on(events.CallbackQuery(data=b"view_start"))
async def view_start(event):

    db = await load_db()

    if db.get("start_message"):
        text = f"📢 Current Start Message:\n\n{db['start_message']}"
    else:
        text = "No Start Message Set."

    await event.edit(
        text,
        buttons=start_menu()
    )


# ================= REMOVE START MESSAGE =================

@userbot.on(events.CallbackQuery(data=b"remove_start"))
async def remove_start(event):

    db = await load_db()

    db["start_message"] = None

    await save_db(db)

    await event.answer("Removed ✅")

    await start_manager(event)


# ================= LINK FILTER MENU =================

@userbot.on(events.CallbackQuery(data=b"link_filter"))
async def link_filter_menu(event):

    db = await load_db()

    buttons = []

    for i, pair in enumerate(db["pairs"]):

        status = "ON" if pair.get("link_filter") else "OFF"

        name = pair.get("name", f"{pair['from']} ➜ {pair['to']}")

        buttons.append(
            [Button.inline(f"{name} ({status})", f"link_{i}".encode())]
        )

    buttons.append([Button.inline("🔙 Back", b"back")])

    await event.edit(
        "Toggle Link Filter",
        buttons=buttons
    )


# ================= LINK FILTER TOGGLE =================

@userbot.on(events.CallbackQuery(pattern=b"link_"))
async def link_toggle(event):

    db = await load_db()

    index = int(event.data.decode().split("_")[1])

    db["pairs"][index]["link_filter"] = not db["pairs"][index].get("link_filter", False)

    await save_db(db)

    await event.answer("Updated")

    await link_filter_menu(event)
    
# ================= AUTO DELETE MENU =================

@userbot.on(events.CallbackQuery(data=b"delete_time"))
async def delete_time_menu(event):

    db = await load_db()

    if not db["pairs"]:
        await event.answer("No pairs added", alert=True)
        return

    buttons = []

    for i, pair in enumerate(db["pairs"]):

        t = pair.get("delete_time", 0)
        status = "OFF" if t == 0 else f"{t}s"

        name = pair.get("name", f"{pair['from']} ➜ {pair['to']}")

        buttons.append([
            Button.inline(f"{name} ({status})", f"set_dtime_{i}".encode())
        ])

    buttons.append([Button.inline("🔙 Back", b"back")])

    await event.edit(
        "⏱ Select Pair to Set Delete Time",
        buttons=buttons
    )


@userbot.on(events.CallbackQuery(pattern=b"set_dtime_"))
async def ask_delete_time(event):

    index = int(event.data.decode().split("_")[2])

    user_states[event.sender_id] = {
        "step": "set_delete_time",
        "pair_index": index
    }

    await event.edit(
        "Send delete time in seconds\n\nExample:\n10 = delete after 10 sec\n0 = disable"
    )


# ================= BUTTON SYSTEM =================

async def build_buttons():

    db = await load_db()

    if not db["buttons"]:
        return None

    buttons = []

    for b in db["buttons"]:
        buttons.append([Button.url(b["text"], b["url"])])

    return buttons


def button_menu():

    return [
        [Button.inline("➕ Add Button", b"add_button")],
        [Button.inline("❌ Remove Button", b"remove_button")],
        [Button.inline("👀 View Buttons", b"view_buttons")],
        [Button.inline("🔙 Back", b"back")]
    ]


# ================= ADMIN COMMANDS =================

@userbot.on(events.NewMessage(pattern="/access"))
async def add_admin(event):

    if event.sender_id != OWNER_ID:
        await event.respond("❌ Only Owner Can Add Admin")
        return

    args = event.raw_text.split()

    if len(args) != 2:
        await event.respond("Usage:\n/access USER_ID")
        return

    try:
        admin_id = int(args[1])
    except:
        await event.respond("Send Valid User ID")
        return

    db = await load_db()

    if admin_id in db["admins"]:
        await event.respond("⚠️ Already Admin")
        return

    db["admins"].append(admin_id)

    await save_db(db)

    await event.respond(f"✅ Admin Added:\n{admin_id}")


@userbot.on(events.NewMessage(pattern="/remove_admin"))
async def remove_admin(event):

    if event.sender_id != OWNER_ID:
        await event.respond("❌ Only Owner Can Remove Admin")
        return

    args = event.raw_text.split()

    if len(args) != 2:
        await event.respond("Usage:\n/remove_admin USER_ID")
        return

    try:
        admin_id = int(args[1])
    except:
        await event.respond("Send Valid User ID")
        return

    db = await load_db()

    if admin_id not in db["admins"]:
        await event.respond("❌ Not Admin")
        return

    db["admins"].remove(admin_id)

    await save_db(db)

    await event.respond(f"✅ Admin Removed:\n{admin_id}")


@userbot.on(events.NewMessage(pattern="/admins"))
async def list_admins(event):

    if event.sender_id != OWNER_ID:
        return

    db = await load_db()

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
        "<code>/admins</code>\n"
    )

    await event.respond(text, parse_mode="html")


# ================= FORWARD SYSTEM =================

@userbot.on(events.NewMessage)
async def forward_handler(event):

    if not event.is_group and not event.is_channel:
        return

    db = await load_db()

    if not db.get("global_enabled", True):
        return

    for pair in db.get("pairs", []):

        if not pair.get("enabled", True):
            continue

        if event.chat_id != pair["from"]:
            continue

        text = event.raw_text or ""

        # 🔗 LINK FILTER
        if pair.get("link_filter"):
            if "http" in text or "t.me" in text or "www." in text:
                print("🔗 Link blocked")
                continue

        try:

            msg = await event.message.forward_to(pair["to"])

            print("✅ Forwarded")

            # 🔘 BUTTON ADD
            buttons = await build_buttons()

            if buttons:
                await userbot.send_message(
                    pair["to"],
                    " ",
                    buttons=buttons
                )

            # ⏱ AUTO DELETE
            delete_time = pair.get("delete_time", 0)

            if delete_time > 0:
                asyncio.create_task(
                    auto_delete(pair["to"], msg.id, delete_time)
                )

        except Exception as e:
            print("❌ Error:", e)


async def auto_delete(chat_id, msg_id, delay):

    await asyncio.sleep(delay)

    try:
        await userbot.delete_messages(chat_id, msg_id)
    except:
        pass


# ================= MAIN =================

async def main():

    print("🚀 Bot Starting...")

    await start_web_server()

    await userbot.start()
    print("✅ Userbot Connected")

    await dp.start_polling(bot)