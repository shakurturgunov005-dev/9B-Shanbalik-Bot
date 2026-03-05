import asyncio
import os
import datetime
import asyncpg
import pytz

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from aiogram import Bot, Dispatcher, types, F
from datetime import datetime, timedelta
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, Update
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import uvicorn
from aiogram.filters import CommandStart

# ================= CONFIG =================

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
DATABASE_URL = os.getenv("DATABASE_URL")

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
    sent = await message.answer(text)
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

# ================= REMINDER =================

async def monthly_reminder():

    student = await get_current_student()

    if not student:
        return

    months = [
        "yanvar","fevral","mart","aprel","may","iyun",
        "iyul","avgust","sentabr","oktabr","noyabr","dekabr"
    ]

    date = student["shanbalik_date"]

    formatted_date = f"{date.day}-{months[date.month-1]} {date.year}"

    text = f"""
📢 Eslatma

Keyingi shanbalik navbati:

👤 {student['name']}
📅 {formatted_date}

Tayyor bo‘ling.
"""

    await bot.send_message(GROUP_ID, text)


async def today_reminder():

    student = await get_current_student()

    if not student:
        return

    today = datetime.now(UZ_TZ).date()

    if student["shanbalik_date"] != today:
        return

    text = f"""
📢 Bugun shanbalik!

👤 {student['name']}

Bugun sizning navbatingiz.
"""

    await bot.send_message(GROUP_ID, text)
    
# ================= COMMANDS =================

@dp.message(CommandStart())
async def start_handler(message: types.Message):

    name = message.from_user.full_name
    is_admin = message.from_user.id in ADMIN_IDS
    role = "ADMIN 👑" if is_admin else "USER"

    text = f"""
━━━━━━━━━━━━━━━━━━
📊 𝐒𝐇𝐀𝐍𝐁𝐀𝐋𝐈𝐊 𝟐𝟎𝟐𝟔
━━━━━━━━━━━━━━━━━━

Assalomu alaykum, {name} 👋
Access Level: {role}
System Status: 🟢 Active
━━━━━━━━━━━━━━━━━━
"""

    await message.answer(
        text,
        reply_markup=admin_keyboard() if is_admin else user_keyboard()
    )

# ================= NAVBAT =================

@dp.message(F.text == "📊 Navbat")
async def navbat(message: types.Message):

    await move_past_students_to_history()

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

    await smart_send(message, text, 180)

# ================= RO‘YXAT =================

@dp.message(F.text == "📋 Ro‘yxat")
async def royxat(message: types.Message):

    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT name FROM students ORDER BY position")

    if not rows:
        await smart_send(message, "Ro‘yxat bo‘sh.", 300)
        return

    text = "━━━━━━━━━━━━━━━━━━\n📋 RO‘YXAT\n━━━━━━━━━━━━━━━━━━\n\n"

    months = [
        "yanvar","fevral","mart","aprel","may","iyun",
        "iyul","avgust","sentabr","oktabr","noyabr","dekabr"
    ]

    start_date = datetime(2026, 4, 1)

    for i, r in enumerate(rows, start=1):

        date = start_date + timedelta(days=i-1)
        formatted_date = f"{date.day}-{months[date.month-1]} {date.year}"

        text += f"{i:>2}. {r['name']:<18} {formatted_date}\n"

    text += "\n━━━━━━━━━━━━━━━━━━"

    await smart_send(message, text, 300)

# ================= TARIX =================

@dp.message(F.text == "📜 Tarix")
async def tarix(message: types.Message):

    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT name, shanbalik_date FROM history ORDER BY id DESC LIMIT 10"
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

    await smart_send(message, text, 300)

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
        birth_date = datetime.datetime.strptime(message.text, "%Y-%m-%d").date()

        async with db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO birthdays (user_id,name,birth_date)
                VALUES ($1,$2,$3)
                ON CONFLICT (user_id) DO NOTHING
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

            next_date = next_first_day()

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

    global db_pool

    db_pool = await asyncpg.create_pool(DATABASE_URL)
    await init_db()
    scheduler.add_job(monthly_reminder, "cron", day=28, hour=6, minute=0)
    scheduler.add_job(today_reminder, "cron", hour=6, minute=0)
    scheduler.start()

    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_webhook(WEBHOOK_URL)


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