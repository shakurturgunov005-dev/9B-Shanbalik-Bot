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

# ================= CONFIG =================

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
GROUP_ID = int(os.getenv("GROUP_ID"))
DATABASE_URL = os.getenv("DATABASE_URL")

ADMIN_IDS = [6042457335]

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
app = FastAPI()
scheduler = AsyncIOScheduler()
db_pool = None

# ================= DATE FORMAT =================

def format_date_uz(date_obj):
    months = {
        1: "yanvar", 2: "fevral", 3: "mart", 4: "aprel",
        5: "may", 6: "iyun", 7: "iyul", 8: "avgust",
        9: "sentyabr", 10: "oktyabr", 11: "noyabr", 12: "dekabr"
    }
    return f"{date_obj.day}-{months[date_obj.month]} {date_obj.year}"

# ================= KEYBOARDS =================

def group_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📅 Navbat")],
            [KeyboardButton(text="📋 Ro‘yxat")],
            [KeyboardButton(text="📚 Tarix")]
        ],
        resize_keyboard=True
    )


def admin_private_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📅 Navbat")],
            [KeyboardButton(text="📋 Ro‘yxat")],
            [KeyboardButton(text="📚 Tarix")],
            [KeyboardButton(text="➕ O‘quvchi qo‘shish")],
            [KeyboardButton(text="❌ O‘quvchi o‘chirish")]
        ],
        resize_keyboard=True
    )

def is_admin(message: types.Message):
    return message.from_user.id in ADMIN_IDS

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
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            user_id BIGINT UNIQUE,
            full_name TEXT,
            username TEXT,
            joined_at TIMESTAMP
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

async def add_user(user):
    async with db_pool.acquire() as conn:
        await conn.execute("""
        INSERT INTO users (user_id, full_name, username, joined_at)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (user_id) DO NOTHING
        """, user.id, user.full_name, user.username, datetime.datetime.utcnow())

async def add_student(name, date):
    async with db_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO students (name, shanbalik_date) VALUES ($1, $2)",
            name, date
        )

async def get_all_students():
    async with db_pool.acquire() as conn:
        return await conn.fetch(
            "SELECT id, name, shanbalik_date FROM students ORDER BY shanbalik_date"
        )

async def get_next_student():
    async with db_pool.acquire() as conn:
        return await conn.fetchrow("""
        SELECT name, shanbalik_date
        FROM students
        WHERE shanbalik_date >= CURRENT_DATE
        ORDER BY shanbalik_date
        LIMIT 1
        """)

async def delete_student_by_id(student_id):
    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM students WHERE id=$1", student_id)

async def archive_completed_shanbalik():
    async with db_pool.acquire() as conn:
        completed = await conn.fetch("""
            SELECT id, name, shanbalik_date
            FROM students
            WHERE shanbalik_date < CURRENT_DATE
        """)

        for row in completed:
            await conn.execute("""
                INSERT INTO shanbalik_history (name, shanbalik_date, completed_at)
                VALUES ($1, $2, $3)
            """, row["name"], row["shanbalik_date"], datetime.datetime.utcnow())

            await conn.execute(
                "DELETE FROM students WHERE id=$1",
                row["id"]
            )

# ================= HANDLERS =================

@dp.message()
async def handle_message(message: types.Message):
    await add_user(message.from_user)
    text = message.text
    if not text:
        return

    # START
    if text == "/start":

    # Agar guruh bo‘lsa
    if message.chat.type in ["group", "supergroup"]:
        return await message.answer(
            "Sinf menyusi 📚",
            reply_markup=group_keyboard()
        )

    # Agar private chat bo‘lsa
    if message.chat.type == "private":

        if is_admin(message):
            return await message.answer(
                "Admin panel 🔐",
                reply_markup=admin_private_keyboard()
            )
        else:
            return await message.answer(
                "Sinf menyusi 📚",
                reply_markup=group_keyboard()
            )

    # NAVBAT
    if text == "📅 Navbat" or text == "/navbat":
        student = await get_next_student()
        if not student:
            return await message.answer("Navbat topilmadi.")
        remaining = (student["shanbalik_date"] - datetime.date.today()).days
        return await message.answer(
            f"{student['name']}\n"
            f"{format_date_uz(student['shanbalik_date'])}\n"
            f"Qolgan kun: {remaining}"
        )

    # LIST
    if text == "📋 Ro‘yxat" or text == "/list":
        students = await get_all_students()
        if not students:
            return await message.answer("Ro‘yxat bo‘sh.")

        for s in students:
            keyboard = None
            if is_admin(message):
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(
                        text="❌ O‘chirish",
                        callback_data=f"delete_{s['id']}"
                    )]
                ])

            await message.answer(
                f"{s['name']} - {format_date_uz(s['shanbalik_date'])}",
                reply_markup=keyboard
            )

    # HISTORY
    if text == "📚 Tarix" or text == "/history":
        async with db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT name, shanbalik_date
                FROM shanbalik_history
                ORDER BY completed_at DESC
                LIMIT 10
            """)

        if not rows:
            return await message.answer("Tarix bo‘sh.")

        msg = "\n".join(
            f"{r['name']} - {format_date_uz(r['shanbalik_date'])}"
            for r in rows
        )
        return await message.answer(msg)

# ================= CALLBACK =================

@dp.callback_query()
async def handle_callback(callback: types.CallbackQuery):
    data = callback.data

    if data.startswith("delete_"):
        student_id = int(data.split("_")[1])
        await delete_student_by_id(student_id)
        await callback.message.edit_text("O‘chirildi ✅")
        await callback.answer()

# ================= REMINDER =================

async def daily_reminder():
    await archive_completed_shanbalik()

    student = await get_next_student()
    if not student:
        return

    remaining = (student["shanbalik_date"] - datetime.date.today()).days

    if remaining == 1:
        await bot.send_message(GROUP_ID, f"Ertaga shanbalik: {student['name']}")

    elif remaining == 0:
        await bot.send_message(GROUP_ID, f"Bugun shanbalik: {student['name']}")

# ================= WEBHOOK =================

@app.post("/webhook")
async def webhook_handler(request: Request):
    data = await request.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return JSONResponse({"ok": True})

@app.on_event("startup")
async def on_startup():
    global db_pool
    db_pool = await asyncpg.create_pool(DATABASE_URL)
    await init_db()

    scheduler.add_job(daily_reminder, "cron", hour=8, minute=0)
    scheduler.start()

    await bot.set_webhook(WEBHOOK_URL)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)