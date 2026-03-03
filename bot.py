import os
import datetime
import asyncpg
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from aiogram import Bot, Dispatcher, types
from aiogram.types import Update
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import uvicorn

# ================= CONFIG =================

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
GROUP_ID = os.getenv("GROUP_ID")
DATABASE_URL = os.getenv("DATABASE_URL")

ADMIN_IDS = [6042457335]

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
app = FastAPI()
scheduler = AsyncIOScheduler()

db_pool = None

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

async def add_user(user):
    async with db_pool.acquire() as conn:
        await conn.execute("""
        INSERT INTO users (user_id, full_name, username, joined_at)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (user_id) DO NOTHING
        """, user.id, user.full_name, user.username, datetime.datetime.utcnow())

async def get_user_count():
    async with db_pool.acquire() as conn:
        return await conn.fetchval("SELECT COUNT(*) FROM users")

async def get_all_users():
    async with db_pool.acquire() as conn:
        return await conn.fetch("SELECT user_id FROM users")

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

async def delete_student_by_name(name):
    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM students WHERE name=$1", name)

# ================= ADMIN =================

def is_admin(message: types.Message):
    return message.from_user.id in ADMIN_IDS

# ================= ERROR MONITORING =================

async def notify_admin_error(error_text: str):
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"🚨 BOT XATOLIK!\n\n{error_text}"
            )
        except:
            pass

# ================= COMMANDS =================

@dp.message()
async def handle_message(message: types.Message):
    try:
        await add_user(message.from_user)
        text = message.text

        if not text:
            return

        # ===== ADMIN PANEL =====
        if text == "/admin":
            if not is_admin(message):
                return await message.answer("Admin emas.")
            count = await get_user_count()
            return await message.answer(
                f"🔐 Admin panel\n👥 Foydalanuvchilar: {count}"
            )

        # ===== START =====
        if text == "/start":
            return await message.answer("Bot 24/7 ishlayapti 🚀")

        # ===== BROADCAST =====
        if text.startswith("/broadcast"):
            if not is_admin(message):
                return await message.answer("Admin emas.")

            msg = text.replace("/broadcast ", "")
            users = await get_all_users()

            for u in users:
                try:
                    await bot.send_message(u["user_id"], msg)
                except:
                    pass

            return await message.answer("Xabar yuborildi ✅")

        # ===== LIST =====
        if text == "/list":
            students = await get_all_students()
            if not students:
                return await message.answer("Ro‘yxat bo‘sh.")

            msg = "\n".join(
                f"{s['id']}. {s['name']} - {s['shanbalik_date']}"
                for s in students
            )
            return await message.answer(msg)

        # ===== NAVBAT =====
        if text == "/navbat":
            student = await get_next_student()
            if not student:
                return await message.answer("Navbat topilmadi.")

            remaining = (student["shanbalik_date"] - datetime.date.today()).days

            return await message.answer(
                f"{student['name']}\n"
                f"Sana: {student['shanbalik_date']}\n"
                f"Qolgan kun: {remaining}"
            )

        # ===== ADD =====
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
                if not month:
                    return await message.answer("Oy noto‘g‘ri yozilgan.")

                date = datetime.date(year, month, day)
                await add_student(name, date)

                return await message.answer("Qo‘shildi ✅")

            except:
                return await message.answer("Format: /add Ali 1 mart 2026")

        # ===== DELETE =====
        if text.startswith("/delete"):
            if not is_admin(message):
                return await message.answer("Admin emas.")

            try:
                value = text.split()[1]

                if value.isdigit():
                    await delete_student_by_id(int(value))
                else:
                    await delete_student_by_name(value)

                return await message.answer("O‘chirildi ✅")

            except:
                return await message.answer("Format: /delete ID yoki Ism")

    except Exception as e:
        error_text = f"{type(e).__name__}: {e}"
        print("ERROR:", error_text)
        await notify_admin_error(error_text)

# ================= REMINDER =================

async def monthly_reminder():
    try:
        student = await get_next_student()
        if student and GROUP_ID:
            await bot.send_message(
                chat_id=int(GROUP_ID),
                text=f"📢 28-kun eslatma:\n{student['name']} - {student['shanbalik_date']}"
            )
    except Exception as e:
        await notify_admin_error(f"REMINDER ERROR: {e}")

# ================= WEBHOOK =================

@app.post("/webhook")
async def webhook_handler(request: Request):
    try:
        data = await request.json()
        update = Update.model_validate(data)
        await dp.feed_update(bot, update)
        return JSONResponse({"ok": True})
    except Exception as e:
        error_text = f"WEBHOOK ERROR: {type(e).__name__}: {e}"
        print(error_text)
        await notify_admin_error(error_text)
        return JSONResponse({"ok": False})

@app.on_event("startup")
async def on_startup():
    global db_pool
    db_pool = await asyncpg.create_pool(DATABASE_URL)
    await init_db()

    scheduler.add_job(monthly_reminder, "cron", day=28, hour=8, minute=0)
    scheduler.start()

    await bot.set_webhook(WEBHOOK_URL)

# ================= RUN =================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)