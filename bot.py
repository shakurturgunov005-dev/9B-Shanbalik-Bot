import os
import datetime
import aiosqlite
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from aiogram import Bot, Dispatcher, types
from aiogram.types import Update
from apscheduler.schedulers.asyncio import AsyncIOScheduler

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
GROUP_ID = os.getenv("GROUP_ID")
ADMIN_USERNAME = "muhibillaevich"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
app = FastAPI()
scheduler = AsyncIOScheduler()

DB_NAME = "shanbalik.db"

# ---------------- DATABASE ----------------

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            shanbalik_date TEXT
        )
        """)
        await db.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER UNIQUE,
    full_name TEXT,
    username TEXT,
    joined_at TEXT
)
""")
        await db.commit()

async def add_student(name, date):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO students (name, shanbalik_date) VALUES (?, ?)",
            (name, date)
        )
        await db.commit()

async def delete_student_by_id(student_id):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM students WHERE id = ?", (student_id,))
        await db.commit()

async def delete_student_by_name(name):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM students WHERE name = ?", (name,))
        await db.commit()

async def get_all_students():
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "SELECT id, name, shanbalik_date FROM students ORDER BY shanbalik_date"
        )
        return await cursor.fetchall()

async def get_next_student():
    today = datetime.date.today().isoformat()
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "SELECT name, shanbalik_date FROM students WHERE shanbalik_date >= ? ORDER BY shanbalik_date LIMIT 1",
            (today,)
        )
        return await cursor.fetchone()

# ---------------- ADMIN ----------------

def is_admin(message: types.Message):
    return message.from_user.username == ADMIN_USERNAME

# ---------------- COMMANDS ----------------

@dp.message()
async def handle_message(message: types.Message):
    text = message.text

    if text == "/start":
        return await message.answer("Bot 24/7 ishlayapti 🚀")

    if text == "/list":
        students = await get_all_students()
        if not students:
            return await message.answer("Ro‘yxat bo‘sh.")
        msg = ""
        for s in students:
            msg += f"{s[0]}. {s[1]} - {s[2]}\n"
        return await message.answer(msg)

    if text == "/navbat":
        student = await get_next_student()
        if not student:
            return await message.answer("Navbat topilmadi.")
        name, date = student
        today = datetime.date.today()
        remaining = (datetime.date.fromisoformat(date) - today).days
        return await message.answer(
            f"{name}\nSana: {date}\nQolgan kun: {remaining}"
        )

    if text.startswith("/add"):
        if not is_admin(message):
            return await message.answer("Admin emas.")
        try:
            parts = text.split()
            name = parts[1]
            day = int(parts[2])
            month_text = parts[3].lower()
            year = int(parts[4])

            months = {
                "yanvar":1,"fevral":2,"mart":3,"aprel":4,
                "may":5,"iyun":6,"iyul":7,"avgust":8,
                "sentyabr":9,"oktyabr":10,"noyabr":11,"dekabr":12
            }

            month = months.get(month_text)
            date = datetime.date(year, month, day)
            await add_student(name, date.isoformat())
            return await message.answer("Qo‘shildi.")
        except:
            return await message.answer("Format: /add Ali 1 mart 2026")

    if text.startswith("/delete"):
        if not is_admin(message):
            return await message.answer("Admin emas.")
        try:
            value = text.split()[1]
            if value.isdigit():
                await delete_student_by_id(int(value))
            else:
                await delete_student_by_name(value)
            return await message.answer("O‘chirildi.")
        except:
            return await message.answer("Format: /delete ID yoki Ism")

# ---------------- REMINDER ----------------

async def monthly_reminder():
    student = await get_next_student()
    if student and GROUP_ID:
        name, date = student
        await bot.send_message(
            chat_id=GROUP_ID,
            text=f"Eslatma: {name} - {date}"
        )

# ---------------- WEBHOOK ----------------

@app.post("/webhook")
async def webhook_handler(request: Request):
    data = await request.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return JSONResponse({"ok": True})

@app.on_event("startup")
async def on_startup():
    await init_db()
    scheduler.add_job(monthly_reminder, "cron", day=28, hour=8, minute=0)
    scheduler.start()
    await bot.set_webhook(WEBHOOK_URL)

@app.on_event("shutdown")
async def on_shutdown():
    await bot.delete_webhook()
    
    import uvicorn
import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)