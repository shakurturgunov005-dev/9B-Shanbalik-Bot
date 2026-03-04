import asyncio
import os
import datetime
import asyncpg
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from aiogram import Bot, Dispatcher, types
from aiogram.types import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import uvicorn
import pytz
print("FILE STARTED")
print("BOT_TOKEN:", os.getenv("BOT_TOKEN"))
print("WEBHOOK_URL:", os.getenv("WEBHOOK_URL"))
print("GROUP_ID:", os.getenv("GROUP_ID"))
print("DATABASE_URL:", os.getenv("DATABASE_URL"))

# ================= CONFIG =================

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
GROUP_ID = int(os.getenv("GROUP_ID"))
DATABASE_URL = os.getenv("DATABASE_URL")

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

async def smart_reply(message, text, seconds=180):
    msg = await message.answer(text, parse_mode="HTML")
    if message.chat.type in ["group", "supergroup"]:
        asyncio.create_task(auto_delete(msg, seconds))
    return msg

# ================= DATABASE =================

async def init_db():
    async with db_pool.acquire() as conn:
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id SERIAL PRIMARY KEY,
            name TEXT,
            shanbalik_date DATE
        )
        """)

        await conn.execute("""
        CREATE TABLE IF NOT EXISTS shanbalik_history (
            id SERIAL PRIMARY KEY,
            name TEXT,
            shanbalik_date DATE,
            completed_at TIMESTAMP
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

# ================= ABOUT =================

@dp.message(lambda m: m.text == "/about")
async def about_handler(message: types.Message):
    msg = (
        "━━━━━━━━━━━━━━━━━━\n"
        "🚀 <b>ShanbalikPro</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "📦 Version: 1.1\n"
        "📅 Project Started: 3 March 2026\n"
        "📍 Saint Petersburg\n\n"
        "Mini-startup edition 🔥\n"
        "━━━━━━━━━━━━━━━━━━"
    )

    sent = await message.answer(msg, parse_mode="HTML")
    asyncio.create_task(auto_delete(sent, 60))

# ================= BIRTHDAY ADD =================

@dp.message(lambda m: m.chat.type == "private")
async def birthday_add(message: types.Message):
    if "tug‘ilgan" in message.text.lower():
        try:
            date_str = message.text.split()[-1]
            birth_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()

            async with db_pool.acquire() as conn:
                await conn.execute(
                    "INSERT INTO birthdays (user_id, name, birth_date) VALUES ($1,$2,$3)",
                    message.from_user.id,
                    message.from_user.full_name,
                    birth_date
                )

            await message.answer("🎂 Tug‘ilgan kun saqlandi!")
        except:
            await message.answer("Format: 2007-05-14")

# ================= BIRTHDAY REMINDER =================

async def birthday_reminder():
    today = datetime.datetime.now(UZ_TZ).date()

    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT name FROM birthdays WHERE EXTRACT(MONTH FROM birth_date)=$1 AND EXTRACT(DAY FROM birth_date)=$2",
            today.month, today.day
        )

    for r in rows:
        msg = (
            "━━━━━━━━━━━━━━━━━━\n"
            "🎉 <b>BUGUN TUG‘ILGAN KUN!</b>\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            f"🎂 <b>{r['name']}</b>\n"
            "Sizni chin qalbimizdan tabriklaymiz!\n"
            "Baxt, sog‘lik va omad tilaymiz! 🥳\n\n"
            "━━━━━━━━━━━━━━━━━━"
        )

        await bot.send_message(GROUP_ID, msg, parse_mode="HTML")

# ================= DAILY REMINDER =================

async def daily_reminder():
    today = datetime.datetime.now(UZ_TZ).date()

    async with db_pool.acquire() as conn:
        student = await conn.fetchrow("""
            SELECT name, shanbalik_date
            FROM students
            WHERE shanbalik_date >= $1
            ORDER BY shanbalik_date
            LIMIT 1
        """, today)

    if not student:
        return

    remaining = (student["shanbalik_date"] - today).days

    if remaining == 1:
        await bot.send_message(GROUP_ID, f"Ertaga shanbalik: {student['name']}")
    elif remaining == 0:
        await bot.send_message(GROUP_ID, f"Bugun shanbalik: {student['name']}")

# ================= STARTUP =================

@app.on_event("startup")
async def on_startup():
    global db_pool
    db_pool = await asyncpg.create_pool(DATABASE_URL)
    await init_db()

    scheduler.add_job(daily_reminder, "cron", hour=8, minute=0)
    scheduler.add_job(birthday_reminder, "cron", hour=6, minute=0)
    scheduler.start()

    await bot.set_webhook(WEBHOOK_URL)

# ================= WEBHOOK =================

@app.post("/webhook")
async def webhook_handler(request: Request):
    data = await request.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return JSONResponse({"ok": True})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)