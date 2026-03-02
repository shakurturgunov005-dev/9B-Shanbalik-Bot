import asyncio
import datetime
import aiosqlite
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = os.getenv("GROUP_ID")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()

DB_NAME = "shanbalik.db"

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            shanbalik_date TEXT
        )
        """)
        await db.commit()

async def get_next_student():
    today = datetime.date.today().isoformat()
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "SELECT name, shanbalik_date FROM students WHERE shanbalik_date >= ? ORDER BY shanbalik_date LIMIT 1",
            (today,)
        )
        return await cursor.fetchone()

@dp.message(Command("start"))
async def start(message: Message):
    await message.answer("🤖 9B Shanbalik bot ishga tushdi!")

@dp.message(Command("navbat"))
async def navbat(message: Message):
    student = await get_next_student()
    if student:
        name, date = student
        today = datetime.date.today()
        remaining = (datetime.date.fromisoformat(date) - today).days
        await message.answer(
            f"🟩 Navbatchi: {name}\n📅 Sana: {date}\n⏳ Qolgan kun: {remaining}"
        )
    else:
        await message.answer("Navbat topilmadi.")

async def reminder():
    student = await get_next_student()
    if student and GROUP_ID:
        name, date = student
        await bot.send_message(
            chat_id=GROUP_ID,
            text=f"🔔 Eslatma!\n{name} ning shanbaligi {date} kuni."
        )

async def main():
    await init_db()
    scheduler.add_job(reminder, "cron", hour=8, minute=0)
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
