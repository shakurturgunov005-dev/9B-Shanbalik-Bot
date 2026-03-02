import datetime
import aiosqlite
import os
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from apscheduler.schedulers.asyncio import AsyncIOScheduler

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = os.getenv("GROUP_ID")
ADMIN_USERNAME = "muhibillaevich"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
scheduler = AsyncIOScheduler()

DB_NAME = "shanbalik.db"

# ---------- DATABASE ----------

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

async def add_student(name, date):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO students (name, shanbalik_date) VALUES (?, ?)",
            (name, date)
        )
        await db.commit()

async def delete_student(student_id):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM students WHERE id = ?", (student_id,))
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

# ---------- ADMIN CHECK ----------

def is_admin(message: types.Message):
    return message.from_user.username == ADMIN_USERNAME

# ---------- COMMANDS ----------

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    await message.answer("🤖 9B Shanbalik Premium Bot ishga tushdi!")

@dp.message_handler(commands=['help'])
async def help_cmd(message: types.Message):
    await message.answer(
        "/navbat - Eng yaqin navbatchi\n"
        "/list - Barcha ro‘yxat\n"
        "Admin: /add Ism YYYY-MM-DD\n"
        "Admin: /delete ID"
    )

@dp.message_handler(commands=['add'])
async def add_cmd(message: types.Message):
    if not is_admin(message):
        return await message.answer("⛔ Siz admin emassiz.")

    try:
        _, name, date = message.text.split()
        datetime.date.fromisoformat(date)
        await add_student(name, date)
        await message.answer("✅ Navbatchi qo‘shildi.")
    except:
        await message.answer("Format: /add Ism YYYY-MM-DD")

@dp.message_handler(commands=['delete'])
async def delete_cmd(message: types.Message):
    if not is_admin(message):
        return await message.answer("⛔ Siz admin emassiz.")

    try:
        _, student_id = message.text.split()
        await delete_student(int(student_id))
        await message.answer("🗑 O‘chirildi.")
    except:
        await message.answer("Format: /delete ID")

@dp.message_handler(commands=['list'])
async def list_cmd(message: types.Message):
    students = await get_all_students()
    if not students:
        return await message.answer("Ro‘yxat bo‘sh.")

    text = "📋 Shanbalik ro‘yxati:\n\n"
    for s in students:
        text += f"{s[0]}. {s[1]} - {s[2]}\n"
    await message.answer(text)

@dp.message_handler(commands=['navbat'])
async def navbat_cmd(message: types.Message):
    student = await get_next_student()
    if not student:
        return await message.answer("Navbat topilmadi.")

    name, date = student
    today = datetime.date.today()
    remaining = (datetime.date.fromisoformat(date) - today).days

    await message.answer(
        f"🟢 Eng yaqin navbatchi:\n\n"
        f"👤 {name}\n"
        f"📅 {date}\n"
        f"⏳ Qolgan kun: {remaining}"
    )

# ---------- MONTHLY REMINDER (28th) ----------

async def monthly_reminder():
    student = await get_next_student()
    if student and GROUP_ID:
        name, date = student
        await bot.send_message(
            chat_id=GROUP_ID,
            text=f"🔔 Eslatma!\n{name} ning shanbaligi {date} kuni."
        )

async def on_startup(dp):
    await init_db()
    scheduler.add_job(monthly_reminder, "cron", day=28, hour=8, minute=0)
    scheduler.start()

if __name__ == "__main__":
    executor.start_polling(dp, on_startup=on_startup)