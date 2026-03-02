import asyncio
import datetime
import aiosqlite
import os
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from apscheduler.schedulers.asyncio import AsyncIOScheduler

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = os.getenv("GROUP_ID")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
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

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    await message.answer("🤖 Bot ishga tushdi!")

if __name__ == "__main__":
    executor.start_polling(dp)
