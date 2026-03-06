import asyncio
import os
import asyncpg
import pytz
import random
from aiogram.types import CallbackQuery
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
group_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="📅 Navbat", callback_data="navbat")],
        [InlineKeyboardButton(text="📋 Ro'yxat", callback_data="royxat")],
        [InlineKeyboardButton(text="📚 Tarix", callback_data="tarix")]
    ]
)
from aiogram.filters import Command
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from aiogram import Bot, Dispatcher, types, F
from datetime import datetime, timedelta
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, Update, BotCommand
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import uvicorn
from aiogram.filters import CommandStart

# ================= CONFIG =================

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
GROUP_ID = -1003557503048
ADMIN_IDS = [6042457335]

UZ_TZ = pytz.timezone("Asia/Tashkent")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
app = FastAPI()
scheduler = AsyncIOScheduler(timezone=UZ_TZ)

db_pool = None

# ================= AUTO DELETE =================

async def auto_delete(message, seconds):
    await asyncio.sleep(seconds)
    try:
        await message.delete()
    except:
        pass


async def smart_send(message, text, seconds):
    sent = await message.answer(text, parse_mode="HTML")
    if message.chat.type in ["group", "supergroup"]:
        asyncio.create_task(auto_delete(sent, seconds))
        asyncio.create_task(auto_delete(message, seconds))
    return sent


# ================= DATABASE =================

async def init_db():
    async with db_pool.acquire() as conn:

        await conn.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE,
            position INTEGER,
            shanbalik_date DATE
        )
        """)

        await conn.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            shanbalik_date DATE NOT NULL,
            completed_at TIMESTAMP DEFAULT NOW()
        )
        """)

        await conn.execute("""
        CREATE TABLE IF NOT EXISTS birthdays (
            id SERIAL PRIMARY KEY,
            user_id BIGINT UNIQUE,
            name TEXT,
            birth_date DATE
        )
        """)


# ================= KEYBOARDS =================

def admin_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Navbat")],
            [KeyboardButton(text="📋 Ro‘yxat")],
            [KeyboardButton(text="📜 Tarix")],
            [KeyboardButton(text="➕ O‘quvchi qo‘shish")]
        ],
        resize_keyboard=True
    )


def user_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📊 Navbat")]],
        resize_keyboard=True
    )


# ================= UTIL =================

async def move_past_students_to_history():
    async with db_pool.acquire() as conn:

        await conn.execute("""
            INSERT INTO history (name, shanbalik_date)
            SELECT name, shanbalik_date
            FROM students
            WHERE shanbalik_date < CURRENT_DATE
        """)

        await conn.execute("""
            DELETE FROM students
            WHERE shanbalik_date < CURRENT_DATE
        """)


def next_first_day():
    today = datetime.now(UZ_TZ)

    if today.month == 12:
        return datetime(today.year + 1, 1, 1).date()

    return datetime(today.year, today.month + 1, 1).date()


async def get_current_student():
    async with db_pool.acquire() as conn:

        student = await conn.fetchrow("""
            SELECT *
            FROM students
            WHERE shanbalik_date >= CURRENT_DATE
            ORDER BY shanbalik_date ASC
            LIMIT 1
        """)

        if not student:
            student = await conn.fetchrow("""
                SELECT *
                FROM students
                ORDER BY shanbalik_date ASC
                LIMIT 1
            """)

        return student

async def reset_rotation_if_empty():

    async with db_pool.acquire() as conn:

        count = await conn.fetchval("SELECT COUNT(*) FROM students")

        if count == 0:

            rows = await conn.fetch("""
                SELECT name
                FROM history
                ORDER BY id
            """)

            if not rows:
                return

            start_date = datetime.now(UZ_TZ).date()

            for i, r in enumerate(rows):

                new_date = start_date + timedelta(days=i)

                await conn.execute(
                    """
                    INSERT INTO students (name, position, shanbalik_date)
                    VALUES ($1,$2,$3)
                    """,
                    r["name"],
                    i + 1,
                    new_date
                )

            await conn.execute("DELETE FROM history")
            
# ================= REMINDER =================

async def monthly_reminder():

    student = await get_current_student()

    if not student:
        return

    today = datetime.now(UZ_TZ).date()
    shanbalik_date = student["shanbalik_date"]

    if (shanbalik_date - today).days != 3:
        return

    months = [
        "yanvar","fevral","mart","aprel","may","iyun",
        "iyul","avgust","sentabr","oktabr","noyabr","dekabr"
    ]

    formatted_date = f"{shanbalik_date.day}-{months[shanbalik_date.month-1]} {shanbalik_date.year}"

    text = f"""
📢 Eslatma

Yaqinlashayotgan shanbalik navbati:

👤 {student['name']}
📅 {formatted_date}

"""

    await bot.send_message(GROUP_ID, text)


async def today_reminder():

    student = await get_current_student()

    if not student:
        return

    today = datetime.now(UZ_TZ).date()

    if student["shanbalik_date"] != today:
        return

    months = [
        "yanvar","fevral","mart","aprel","may","iyun",
        "iyul","avgust","sentabr","oktabr","noyabr","dekabr"
    ]

    formatted_date = f"{today.day}-{months[today.month-1]} {today.year}"

    text = f"""
📢 Bugun shanbalik

👤 {student['name']}
📅 {formatted_date}
"""

    await bot.send_message(GROUP_ID, text)
    
#================JUMA TABRIK================

import random

RAMAZON_START = datetime(2026, 2, 18).date()
RAMAZON_END = datetime(2026, 3, 19).date()


ramadan_friday_messages = [
"""🌙 Ramazon muborak!

Bugun muborak juma kuni.
Ro‘za tutayotgan barcha musulmonlarning
ro‘zalarini Alloh qabul qilsin 🤲

✨ Juma muborak!""",

"""🌙 Ramazonning muborak juma kuni!

Alloh tutgan ro‘zalaringizni,
qilgan ibodatlaringizni qabul qilsin.

🤲 Juma muborak!""",

"""🌙 Ramazon oyidagi muborak juma!

Duolaringiz ijobat,
ro‘zalaringiz qabul bo‘lsin.

✨ Juma muborak!"""
]


normal_friday_messages = [
"""🌙 Assalomu alaykum

Bugun muborak juma kuni.
Alloh barcha musulmonlarning
duolarini qabul qilsin.

✨ Juma muborak!""",

"""🤲 Juma ayyomi muborak bo‘lsin!

Alloh qilgan ibodatlaringizni
qabul qilsin.""",

"""🌙 Hayrli juma!

Bugun qilgan duolaringiz,
niyatlaringiz ijobat bo‘lsin."""
]


async def friday_greeting():

    today = datetime.now(UZ_TZ).date()

    # Ramazon tekshirish
    if RAMAZON_START <= today <= RAMAZON_END:
        text = random.choice(ramadan_friday_messages)

    else:
        text = random.choice(normal_friday_messages)

    await bot.send_message(GROUP_ID, text)

async def set_commands(bot):

    commands = [
        BotCommand(command="navbat", description="Navbatni ko‘rish"),
        BotCommand(command="royxat", description="Ro‘yxat"),
        BotCommand(command="tarix", description="Tarix"),
        BotCommand(command="about", description="Bot haqida")
    ]

    await bot.set_my_commands(commands)
    
# ================= MENYU =================
    
async def set_commands(bot):

    commands = [

        BotCommand(
            command="start",
            description="Botni ishga tushirish"
        ),

        BotCommand(
            command="navbat",
            description="Hozirgi shanbalik navbati"
        ),

        BotCommand(
            command="royxat",
            description="Shanbalik ro‘yxati"
        ),

        BotCommand(
            command="tarix",
            description="O‘tgan shanbaliklar"
        ),

        BotCommand(
            command="about",
            description="Bot haqida ma'lumot"
        ),

        BotCommand(
            command="id",
            description="Sizning Telegram ID"
        ),

        BotCommand(
            command="ping",
            description="Bot ishlayotganini tekshirish"
        )

    ]

    await bot.set_my_commands(commands)
    
# ================= COMMANDS =================

@dp.message(CommandStart())
async def start_handler(message: types.Message):

    name = message.from_user.full_name
    is_admin = message.from_user.id in ADMIN_IDS
    role = "ADMIN 👑" if is_admin else "USER"

    text = f"""
━━━━━━━━━━━━━━━━━━
📊 SHANBALIK 2026
━━━━━━━━━━━━━━━━━━

Assalomu alaykum, {name} 👋
Access Level: {role}
System Status: 🟢 Active
━━━━━━━━━━━━━━━━━━
"""

if message.chat.type == "private":
    await message.answer(
        text,
        reply_markup=admin_keyboard() if is_admin else group_keyboard
    )
else:
    await message.answer(
        text,
        reply_markup=group_keyboard
    )
# ================= ABOUT =================

@dp.message(Command("about"))
async def about(message: types.Message):

    text = """
🤖 BOT HAQIDA

📌 Shanbalik navbat bot
📅 Navbatlarni avtomatik yuritadi
⏰ Eslatmalar yuboradi

👨‍💻 Developer: Shukurullo
⚙️ Version: 1.1
"""

    await message.answer(text)

# ================= ID ======================

@dp.message(Command("id"))
async def get_id(message: types.Message):

    text = f"""
🆔 Sizning ID: {message.from_user.id}
💬 Chat ID: {message.chat.id}
"""

    await message.answer(text)

# ================= PING =================

@dp.message(F.text == "/ping")
async def ping(message: types.Message):

    text = """
🏓 BOT STATUS

⚙️ System: Active
🤖 Bot: Working
📡 Connection: OK
"""

    await message.answer(text)

# ================= NAVBAT =================

@dp.message(F.text == "📊 Navbat")
@dp.message(F.text == "/navbat")
async def navbat(message: types.Message):
    
    await move_past_students_to_history()
    await reset_rotation_if_empty()
    
    student = await get_current_student()

    if not student:
        await smart_send(message, "Ro’yxat bo‘sh.", 180)
        return

    months = [
        "yanvar","fevral","mart","aprel","may","iyun",
        "iyul","avgust","sentabr","oktabr","noyabr","dekabr"
    ]

    today = datetime.now(UZ_TZ).date()
    next_date = student["shanbalik_date"]

    days_left = (next_date - today).days

    formatted_date = f"{next_date.day}-{months[next_date.month-1]} {next_date.year}"

    text = "━━━━━━━━━━━━━━━━━━\n"
    text += "📊 NAVBAT\n"
    text += "━━━━━━━━━━━━━━━━━━\n\n"

    text += f"👤 {student['name']:<18}\n"
    text += f"📅 {formatted_date:<18}\n"
    text += f"⏳ {days_left} kun qoldi\n"

    text += "\n━━━━━━━━━━━━━━━━━━"

    await smart_send(message, f"<pre>{text}</pre>", 180)

# ================= RO‘YXAT =================

@dp.message(F.text == "📋 Ro‘yxat")
@dp.message(F.text == "/royxat")
async def royxat(message: types.Message):

    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT name, shanbalik_date FROM students ORDER BY position")

    if not rows:
        await smart_send(message, "Ro‘yxat bo‘sh.", 300)
        return

    text = "━━━━━━━━━━━━━━━━━━\n📋 RO‘YXAT\n━━━━━━━━━━━━━━━━━━\n\n"

    months = [
        "yanvar","fevral","mart","aprel","may","iyun",
        "iyul","avgust","sentabr","oktabr","noyabr","dekabr"
    ]

    for i, r in enumerate(rows, start=1):
        
        date = r["shanbalik_date"]
        formatted_date = f"{date.day}-{months[date.month-1]} {date.year}"

        text += f"{i:>2}. {r['name']:<18} {formatted_date}\n"

    text += "\n━━━━━━━━━━━━━━━━━━"
    
    await smart_send(message, f"<pre>{text}</pre>", 300)

# ================= TARIX =================

@dp.message(F.text == "📜 Tarix")
@dp.message(F.text == "/tarix")
async def tarix(message: types.Message):

    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT name, shanbalik_date FROM history ORDER BY id ASC LIMIT 10"
        )

    if not rows:
        await smart_send(message, "Tarix bo‘sh.", 300)
        return

    text = "━━━━━━━━━━━━━━━━━━\n📜 TARIX\n━━━━━━━━━━━━━━━━━━\n\n"

    months = [
        "yanvar","fevral","mart","aprel","may","iyun",
        "iyul","avgust","sentabr","oktabr","noyabr","dekabr"
    ]

    for i, r in enumerate(rows, start=1):

        date = r["shanbalik_date"]
        formatted_date = f"{date.day}-{months[date.month-1]} {date.year}"

        text += f"{i:>2}. {r['name']:<18} {formatted_date}\n"

    text += "\n━━━━━━━━━━━━━━━━━━"

    await smart_send(message, f"<pre>{text}</pre>", 300)

# ================= ADD STUDENT =================

@dp.message(F.text == "➕ O‘quvchi qo‘shish")
async def ask_student(message: types.Message):

    if message.from_user.id not in ADMIN_IDS:
        return

    await message.answer("Ismini yuboring (private tavsiya qilinadi):")


# ================= PRIVATE HANDLER =================

@dp.message(
    F.chat.type == "private",
    F.text,
    ~F.text.startswith("/"),
    ~F.text.in_([
        "📊 Navbat",
        "📋 Ro‘yxat",
        "📜 Tarix",
        "➕ O‘quvchi qo‘shish"
    ])
)
async def catch_private(message: types.Message):

    # 🎂 Birthday
    try:
        birth_date = datetime.strptime(message.text, "%Y-%m-%d").date()

        async with db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO birthdays (user_id,name,birth_date)
                VALUES ($1,$2,$3)
                ON CONFLICT DO NOTHING
            """,
            message.from_user.id,
            message.from_user.full_name,
            birth_date)

        await message.answer("🎂 Tug‘ilgan kun saqlandi!")
        return

    except:
        pass

    # ➕ Add student
    if message.from_user.id in ADMIN_IDS:

        async with db_pool.acquire() as conn:

            count = await conn.fetchval("SELECT COUNT(*) FROM students")

            today = datetime.now(UZ_TZ).date()
            next_date = today + timedelta(days=count)

            await conn.execute(
                """INSERT INTO students (name, position, shanbalik_date)
                   VALUES ($1,$2,$3)
                   ON CONFLICT (name) DO NOTHING""",
                message.text,
                count + 1,
                next_date
            )

        await message.answer("✅ Qo‘shildi")


# ================= STARTUP =================

@app.on_event("startup")
async def startup():
    await set_commands(bot)

    global db_pool
    
    db_pool = await asyncpg.create_pool(DATABASE_URL)
    await init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_webhook(WEBHOOK_URL)
    
    scheduler.add_job(monthly_reminder, "cron", day=1, hour=9, minute=0)
    scheduler.add_job(today_reminder, "cron", hour=7, minute=0)
    scheduler.add_job(friday_greeting, "cron", day_of_week="fri", hour=9, minute=0)
    
    
    scheduler.start()

#=================main.py===================
    
@dp.callback_query()
async def inline_buttons(callback: CallbackQuery):

    if callback.data == "navbat":
        await callback.message.answer("📅 Bugungi navbatchi: ...")

    elif callback.data == "royxat":
        await callback.message.answer("📋 Talabalar ro'yxati")

    elif callback.data == "tarix":
        await callback.message.answer("📚 Navbatchilik tarixi")

    await callback.answer()
    
# ================= WEBHOOK =================

@app.post("/webhook")
async def webhook(request: Request):

    data = await request.json()

    try:
        update = Update.model_validate(data)
        await dp.feed_update(bot, update)

        return JSONResponse({"ok": True})

    except Exception as e:
        import traceback
        traceback.print_exc()

        return JSONResponse({"error": str(e)}, status_code=500)

# ================= RUN =================

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
    
    