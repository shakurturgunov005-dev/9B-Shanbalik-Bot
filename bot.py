import asyncio
import os
import datetime
import asyncpg
import pytz

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import uvicorn

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
            position INTEGER
        )
        """)

        await conn.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id SERIAL PRIMARY KEY,
            name TEXT,
            month DATE
        )
        """)

        await conn.execute("""
        CREATE TABLE IF NOT EXISTS birthdays (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
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
        keyboard=[
            [KeyboardButton(text="📊 Navbat")]
        ],
        resize_keyboard=True
    )

# ================= UTIL =================

def next_first_day():
    today = datetime.datetime.now(UZ_TZ)
    if today.month == 12:
        return datetime.date(today.year + 1, 1, 1)
    return datetime.date(today.year, today.month + 1, 1)

async def get_current_student():
    async with db_pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT * FROM students ORDER BY position LIMIT 1"
        )

async def rotate_students():
    async with db_pool.acquire() as conn:
        students = await conn.fetch("SELECT * FROM students ORDER BY position")
        if len(students) < 2:
            return

        first = students[0]

        await conn.execute("UPDATE students SET position = position - 1")
        await conn.execute(
            "UPDATE students SET position = $1 WHERE id = $2",
            len(students),
            first["id"]
        )

        await conn.execute(
            "INSERT INTO history (name, month) VALUES ($1,$2)",
            first["name"],
            datetime.date.today()
        )

# ================= START / COMMANDS =================

@dp.message(F.text.startswith("/"))
async def commands(message: types.Message):

    if message.text == "/start":
        name = message.from_user.full_name
        is_admin = message.from_user.id in ADMIN_IDS
        role = "ADMIN 👑" if is_admin else "USER"

        text = f"""
━━━━━━━━━━━━━━━━━━
𝐒𝐇𝐀𝐍𝐁𝐀𝐋𝐈𝐊 𝐏𝐑𝐎
School Automation System
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

    if message.chat.type in ["group", "supergroup"]:
        asyncio.create_task(auto_delete(message, 180))

# ================= NAVBAT =================

@dp.message(F.text == "📊 Navbat")
async def navbat(message: types.Message):
    student = await get_current_student()
    if not student:
        await smart_send(message, "Ro‘yxat bo‘sh.", 180)
        return

    next_date = next_first_day()
    days_left = (next_date - datetime.date.today()).days

    text = f"""
━━━━━━━━━━━━━━━━━━
📊 NAVBAT
━━━━━━━━━━━━━━━━━━

👤 {student['name']}
📅 Sana: {next_date}
⏳ Qolgan kun: {days_left} kun
━━━━━━━━━━━━━━━━━━
"""
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
    for i, r in enumerate(rows, start=1):
        text += f"{i}. {r['name']}\n"
    text += "\n━━━━━━━━━━━━━━━━━━"

    await smart_send(message, text, 300)

# ================= TARIX =================

@dp.message(F.text == "📜 Tarix")
async def tarix(message: types.Message):
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT name, month FROM history ORDER BY id DESC LIMIT 10"
        )

    if not rows:
        await smart_send(message, "Tarix bo‘sh.", 300)
        return

    text = "━━━━━━━━━━━━━━━━━━\n📜 TARIX\n━━━━━━━━━━━━━━━━━━\n\n"
    for r in rows:
        text += f"{r['name']} — {r['month']}\n"
    text += "\n━━━━━━━━━━━━━━━━━━"

    await smart_send(message, text, 300)

# ================= ADD STUDENT =================

@dp.message(F.text == "➕ O‘quvchi qo‘shish")
async def ask_student(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer("Ismini yuboring (private tavsiya qilinadi):")

@dp.message()
async def catch_text(message: types.Message):

    # 🎂 Birthday private format: YYYY-MM-DD
    if message.chat.type == "private":
        try:
            birth_date = datetime.datetime.strptime(message.text, "%Y-%m-%d").date()
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

    # Add student (admin)
    if message.from_user.id in ADMIN_IDS:
        async with db_pool.acquire() as conn:
            count = await conn.fetchval("SELECT COUNT(*) FROM students")
            await conn.execute(
                "INSERT INTO students (name, position) VALUES ($1,$2) ON CONFLICT DO NOTHING",
                message.text,
                count + 1
            )
        await message.answer("✅ Qo‘shildi")

# ================= REMINDERS =================

async def first_day_reminder():
    student = await get_current_student()
    if student:
        await bot.send_message(GROUP_ID, f"📢 Bugun shanbalik: {student['name']}")

async def rotation_job():
    await rotate_students()
    await bot.send_message(GROUP_ID, "🔄 Navbat avtomatik aylantirildi.")

async def reminder_28():
    student = await get_current_student()
    if student:
        await bot.send_message(GROUP_ID, f"⏰ 3 kundan keyin shanbalik: {student['name']}")

async def birthday_reminder():
    today = datetime.date.today()
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT name FROM birthdays
            WHERE EXTRACT(MONTH FROM birth_date) = $1
            AND EXTRACT(DAY FROM birth_date) = $2
        """, today.month, today.day)

    for r in rows:
        await bot.send_message(
            GROUP_ID,
            f"🎉 Bugun {r['name']} ning tug‘ilgan kuni!"
        )

# ================= STARTUP =================

@app.on_event("startup")
async def startup():
    global db_pool
    db_pool = await asyncpg.create_pool(DATABASE_URL)
    await init_db()

    scheduler.add_job(first_day_reminder, "cron", day=1, hour=6, minute=0)
    scheduler.add_job(rotation_job, "cron", day=1, hour=22, minute=0)
    scheduler.add_job(reminder_28, "cron", day=28, hour=6, minute=0)
    scheduler.add_job(birthday_reminder, "cron", hour=6, minute=5)

    scheduler.start()
    await bot.set_webhook(WEBHOOK_URL)

# ================= WEBHOOK =================

@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    await dp.feed_raw_update(bot, data)
    return JSONResponse({"ok": True})

# ================= RUN =================

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))