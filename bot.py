import asyncio
import os
import datetime
import asyncpg
import pytz

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import uvicorn

# ================== CONFIG ==================

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
DATABASE_URL = os.getenv("DATABASE_URL")
GROUP_ID = int(os.getenv("GROUP_ID"))

UZ_TZ = pytz.timezone("Asia/Tashkent")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
app = FastAPI()
scheduler = AsyncIOScheduler(timezone=UZ_TZ)

db_pool = None

# ================== KEYBOARD ==================

main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📅 Navbat")],
        [KeyboardButton(text="📋 Ro’yxat")],
        [KeyboardButton(text="📚 Tarix")],
    ],
    resize_keyboard=True
)

# ================== DATABASE ==================

async def init_db():
    async with db_pool.acquire() as conn:
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            shanbalik_date DATE NOT NULL
        )
        """)

        await conn.execute("""
        CREATE TABLE IF NOT EXISTS shanbalik_history (
            id SERIAL PRIMARY KEY,
            name TEXT,
            completed_at TIMESTAMP DEFAULT NOW()
        )
        """)

# ================== START ==================

@dp.message(F.text == "/start")
async def start_handler(message: types.Message):
    await message.answer(
        "Shanbalik botiga xush kelibsiz!",
        reply_markup=main_keyboard
    )

# ================== ABOUT ==================

@dp.message(F.text == "/about")
async def about_handler(message: types.Message):
    msg = (
        "━━━━━━━━━━━━━━━━━━\n"
        "🚀 <b>ShanbalikPro</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "📦 Version: 2.0\n"
        "📅 Project Started: 3 March 2026\n"
        "⚙️ Powered by FastAPI + Aiogram\n\n"
        "Mini-startup edition 🔥\n"
        "━━━━━━━━━━━━━━━━━━"
    )
    await message.answer(msg, parse_mode="HTML")

# ================== NAVBAT ==================

@dp.message(F.text.contains("Navbat"))
async def navbat_handler(message: types.Message):
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
        await message.answer("Navbat topilmadi.")
        return

    remaining = (student["shanbalik_date"] - today).days

    await message.answer(
        f"📅 Keyingi shanbalik:\n\n"
        f"👤 {student['name']}\n"
        f"📆 {student['shanbalik_date']}\n"
        f"⏳ Qolgan kun: {remaining}"
    )

# ================== RO’YXAT ==================

@dp.message(F.text.contains("Ro’yxat"))
async def royxat_handler(message: types.Message):
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT name, shanbalik_date
            FROM students
            ORDER BY shanbalik_date
        """)

    if not rows:
        await message.answer("Ro‘yxat bo‘sh.")
        return

    text = "📋 Shanbalik ro‘yxati:\n\n"
    for r in rows:
        text += f"👤 {r['name']} — {r['shanbalik_date']}\n"

    await message.answer(text)

# ================== TARIX ==================

@dp.message(F.text.contains("Tarix"))
async def tarix_handler(message: types.Message):
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT name, completed_at
            FROM shanbalik_history
            ORDER BY completed_at DESC
            LIMIT 10
        """)

    if not rows:
        await message.answer("Tarix bo‘sh.")
        return

    text = "📚 Oxirgi bajarilganlar:\n\n"
    for r in rows:
        text += f"👤 {r['name']} — {r['completed_at'].date()}\n"

    await message.answer(text)

# ================== DAILY REMINDER ==================

async def daily_reminder():
    today = datetime.datetime.now(UZ_TZ).date()

    async with db_pool.acquire() as conn:
        student = await conn.fetchrow("""
            SELECT name, shanbalik_date
            FROM students
            WHERE shanbalik_date = $1
            LIMIT 1
        """, today)

    if student:
        await bot.send_message(
            GROUP_ID,
            f"Bugun shanbalik: {student['name']}"
        )

# ================== STARTUP ==================

@app.on_event("startup")
async def on_startup():
    global db_pool

    db_pool = await asyncpg.create_pool(DATABASE_URL)
    await init_db()

    scheduler.add_job(daily_reminder, "cron", hour=8, minute=0)
    scheduler.start()

    await bot.set_webhook(WEBHOOK_URL)

# ================== WEBHOOK ==================

@app.post("/webhook")
async def webhook_handler(request: Request):
    data = await request.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return JSONResponse({"ok": True})

# ================== RUN ==================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)