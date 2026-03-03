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

async def get_user_count():
    async with db_pool.acquire() as conn:
        return await conn.fetchval("SELECT COUNT(*) FROM users")

async def get_today_users():
    async with db_pool.acquire() as conn:
        return await conn.fetchval("""
            SELECT COUNT(*) FROM users
            WHERE DATE(joined_at) = CURRENT_DATE
        """)

async def get_last_7_days_users():
    async with db_pool.acquire() as conn:
        return await conn.fetchval("""
            SELECT COUNT(*) FROM users
            WHERE joined_at >= CURRENT_DATE - INTERVAL '7 days'
        """)

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

# ================= ADMIN =================

def is_admin(message: types.Message):
    return message.from_user.id in ADMIN_IDS

# ================= COMMANDS =================

@dp.message()
async def handle_message(message: types.Message):
    try:
        await add_user(message.from_user)
        text = message.text

        if not text:
            return

        if text == "/start":
            return await message.answer("Bot 24/7 ishlayapti 🚀")

        if text == "/admin":
            if not is_admin(message):
                return await message.answer("Admin emas.")

            total = await get_user_count()
            today = await get_today_users()
            last7 = await get_last_7_days_users()
            next_student = await get_next_student()

            if next_student:
                days_left = (next_student["shanbalik_date"] - datetime.date.today()).days
                navbat_info = f"{next_student['name']} ({days_left} kun qoldi)"
            else:
                navbat_info = "Navbat topilmadi"

            return await message.answer(
                f"🔐 ADMIN PANEL\n\n"
                f"👥 Umumiy: {total}\n"
                f"📅 Bugun: {today}\n"
                f"📈 7 kun: {last7}\n"
                f"🗓 Navbat: {navbat_info}"
            )

        if text == "/list":
            students = await get_all_students()
            if not students:
                return await message.answer("Ro‘yxat bo‘sh.")

            msg = "\n".join(
                f"{s['id']}. {s['name']} - {format_date_uz(s['shanbalik_date'])}"
                for s in students
            )
            return await message.answer(msg)

        if text == "/navbat":
            student = await get_next_student()
            if not student:
                return await message.answer("Navbat topilmadi.")

            remaining = (student["shanbalik_date"] - datetime.date.today()).days
            formatted_date = format_date_uz(student["shanbalik_date"])

            return await message.answer(
                f"{student['name']}\n"
                f"Sana: {formatted_date}\n"
                f"Qolgan kun: {remaining}"
            )

        if text == "/history":
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
            return await message.answer(f"📚 Oxirgi 10 ta:\n\n{msg}")

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
                    return await message.answer("Oy noto‘g‘ri.")

                date = datetime.date(year, month, day)
                await add_student(name, date)

                return await message.answer("Qo‘shildi ✅")

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

                return await message.answer("O‘chirildi ✅")

            except:
                return await message.answer("Format: /delete ID yoki Ism")

    except Exception as e:
        print("ERROR:", e)

# ================= REMINDER =================

async def daily_reminder():
    await archive_completed_shanbalik()

    student = await get_next_student()
    if not student:
        return

    today = datetime.date.today()
    target_date = student["shanbalik_date"]
    remaining = (target_date - today).days
    formatted_date = format_date_uz(target_date)

    if remaining == 3:
        await bot.send_message(GROUP_ID, f"⏳ 3 kun qoldi!\n{student['name']}\n{formatted_date}")

    elif remaining == 1:
        await bot.send_message(GROUP_ID, f"⚠️ Ertaga!\n{student['name']}\n{formatted_date}")

    elif remaining == 0:
        await bot.send_message(GROUP_ID, f"📢 Bugun!\n{student['name']}")

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