import asyncio
import os
import asyncpg
import pytz
import random
from datetime import datetime, timedelta
from urllib.parse import urlparse  # BU QATOR MUHIM!

from aiogram import Bot, Dispatcher, types, F
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, BotCommand
)
from aiogram.filters import Command, CommandStart
from aiogram.fsm.storage.memory import MemoryStorage

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import uvicorn

# ================= CONFIG =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# MUHIM: DATABASE URL NI TO'G'RIDAN-TO'G'RI YOZAMIZ
DATABASE_URL = "postgresql://postgres:QfIuxRfbwyKyLdrnOiexCsVnVzmneCuY@metro.proxy.rlwy.net:31961/railway"

# Database URL ni tekshirish
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

print(f"📦 Database URL: {DATABASE_URL[:30]}...")  # Logga yozish

GROUP_ID = -1003557503048
ADMIN_IDS = [6042457335]

UZ_TZ = pytz.timezone("Asia/Tashkent")

# Bot sozlamalari
storage = MemoryStorage()
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=storage)
app = FastAPI()
scheduler = AsyncIOScheduler(timezone=UZ_TZ)

db_pool = None

# ================= KEYBOARDS =================

# GURUH UCHUN REPLY KEYBOARD (⬜️ BOSGANDA CHIQADI)
group_reply_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📊 Navbat"), KeyboardButton(text="📋 Ro‘yxat"), KeyboardButton(text="📜 Tarix")]
    ],
    resize_keyboard=True,
    is_persistent=True
)

# INLINE KEYBOARD (agar xabar ichida kerak bo'lsa)
group_inline_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="📅 Navbat", callback_data="navbat")],
        [InlineKeyboardButton(text="📋 Ro'yxat", callback_data="royxat")],
        [InlineKeyboardButton(text="📚 Tarix", callback_data="tarix")]
    ]
)

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
        keyboard=[[KeyboardButton(text="📊 Navbat")]],
        resize_keyboard=True
    )

# ================= AUTO DELETE =================
async def auto_delete(message: Message, seconds: int):
    await asyncio.sleep(seconds)
    try:
        await message.delete()
    except:
        pass

async def smart_send(message: Message, text: str, seconds: int):
    sent = await message.answer(text, parse_mode="HTML")
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
            position INTEGER,
            shanbalik_date DATE
        )
        """)

        await conn.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            shanbalik_date DATE NOT NULL,
            completed_at TIMESTAMP DEFAULT NOW()
        )
        """)

        await conn.execute("""
        CREATE TABLE IF NOT EXISTS birthdays (
            id SERIAL PRIMARY KEY,
            user_id BIGINT UNIQUE,
            name TEXT,
            birth_date DATE
        )
        """)

# ================= UTIL FUNCTIONS =================
async def move_past_students_to_history():
    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO history (name, shanbalik_date)
            SELECT name, shanbalik_date
            FROM students
            WHERE shanbalik_date < CURRENT_DATE
        """)
        await conn.execute("""
            DELETE FROM students
            WHERE shanbalik_date < CURRENT_DATE
        """)

async def get_current_student():
    async with db_pool.acquire() as conn:
        student = await conn.fetchrow("""
            SELECT *
            FROM students
            WHERE shanbalik_date >= CURRENT_DATE
            ORDER BY shanbalik_date ASC
            LIMIT 1
        """)
        if not student:
            student = await conn.fetchrow("""
                SELECT *
                FROM students
                ORDER BY shanbalik_date ASC
                LIMIT 1
            """)
        return student

async def reset_rotation_if_empty():
    async with db_pool.acquire() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM students")
        if count == 0:
            rows = await conn.fetch("SELECT name FROM history ORDER BY id")
            if not rows:
                return
            start_date = datetime.now(UZ_TZ).date()
            for i, r in enumerate(rows):
                new_date = start_date + timedelta(days=i)
                await conn.execute(
                    "INSERT INTO students (name, position, shanbalik_date) VALUES ($1,$2,$3)",
                    r["name"], i + 1, new_date
                )
            await conn.execute("DELETE FROM history")

# ================= REMINDER FUNCTIONS =================
async def monthly_reminder():
    student = await get_current_student()
    if not student:
        return
    today = datetime.now(UZ_TZ).date()
    shanbalik_date = student["shanbalik_date"]
    if (shanbalik_date - today).days != 3:
        return
    
    months = ["yanvar","fevral","mart","aprel","may","iyun",
              "iyul","avgust","sentabr","oktabr","noyabr","dekabr"]
    formatted_date = f"{shanbalik_date.day}-{months[shanbalik_date.month-1]} {shanbalik_date.year}"
    
    text = f"""
📢 Eslatma

Yaqinlashayotgan shanbalik navbati:

👤 {student['name']}
📅 {formatted_date}
"""
    await bot.send_message(chat_id=GROUP_ID, text=text)

async def today_reminder():
    student = await get_current_student()
    if not student:
        return
    today = datetime.now(UZ_TZ).date()
    if student["shanbalik_date"] != today:
        return
    
    months = ["yanvar","fevral","mart","aprel","may","iyun",
              "iyul","avgust","sentabr","oktabr","noyabr","dekabr"]
    formatted_date = f"{today.day}-{months[today.month-1]} {today.year}"
    
    text = f"""
📢 Bugun shanbalik

👤 {student['name']}
📅 {formatted_date}
"""
    await bot.send_message(chat_id=GROUP_ID, text=text)

# ================= JUMA TABRIKLAR =================
RAMAZON_START = datetime(2026, 2, 18).date()
RAMAZON_END = datetime(2026, 3, 19).date()

ramadan_friday_messages = [
    "🌙 Ramazon muborak!\n\nBugun muborak juma kuni.\nRo'za tutayotgan barcha musulmonlarning\nro'zalarini Alloh qabul qilsin 🤲\n\n✨ Juma muborak!",
    "🌙 Ramazonning muborak juma kuni!\n\nAlloh tutgan ro'zalaringizni,\nqilgan ibodatlaringizni qabul qilsin.\n\n🤲 Juma muborak!",
    "🌙 Ramazon oyidagi muborak juma!\n\nDuolaringiz ijobat,\nro'zalaringiz qabul bo'lsin.\n\n✨ Juma muborak!"
]

normal_friday_messages = [
    "🌙 Assalomu alaykum\n\nBugun muborak juma kuni.\nAlloh barcha musulmonlarning\nduolarini qabul qilsin.\n\n✨ Juma muborak!",
    "🤲 Juma ayyomi muborak bo'lsin!\n\nAlloh qilgan ibodatlaringizni\nqabul qilsin.",
    "🌙 Hayrli juma!\n\nBugun qilgan duolaringiz,\nniyatlaringiz ijobat bo'lsin."
]

async def friday_greeting():
    today = datetime.now(UZ_TZ).date()
    if RAMAZON_START <= today <= RAMAZON_END:
        text = random.choice(ramadan_friday_messages)
    else:
        text = random.choice(normal_friday_messages)
    await bot.send_message(chat_id=GROUP_ID, text=text)

# ================= COMMAND HANDLERS =================
@dp.message(CommandStart())
async def start_handler(message: Message):
    name = message.from_user.full_name
    is_admin = message.from_user.id in ADMIN_IDS
    role = "ADMIN 👑" if is_admin else "USER"
    
    text = f"""
━━━━━━━━━━━━━━━━━━
📊 SHANBALIK 2026
━━━━━━━━━━━━━━━━━━

Assalomu alaykum, {name} 👋
Access Level: {role}
System Status: 🟢 Active
━━━━━━━━━━━━━━━━━━
"""
    
    if message.chat.type == "private":
        await message.answer(
            text,
            reply_markup=admin_keyboard() if is_admin else user_keyboard()
        )
    else:
        # GURUH UCHUN - PASTDAGI TUGMALAR
        await message.answer(text, reply_markup=group_reply_keyboard)

# CALLBACK HANDLER (INLINE TUGMALAR UCHUN)
@dp.callback_query()
async def inline_buttons_handler(callback: CallbackQuery):
    try:
        if callback.data == "navbat":
            await navbat(callback.message)
        elif callback.data == "royxat":
            await royxat(callback.message)
        elif callback.data == "tarix":
            await tarix(callback.message)
        
        await callback.answer()
    except Exception as e:
        await callback.answer(text=f"Xatolik: {str(e)}", show_alert=True)

@dp.message(Command("about"))
async def about(message: Message):
    text = """
🤖 BOT HAQIDA

📌 Shanbalik navbat bot
📅 Navbatlarni avtomatik yuritadi
⏰ Eslatmalar yuboradi

👨‍💻 Developer: Shukurullo
⚙️ Version: 1.3
"""
    await message.answer(text)

@dp.message(Command("id"))
async def get_id(message: Message):
    text = f"""
🆔 Sizning ID: {message.from_user.id}
💬 Chat ID: {message.chat.id}
"""
    await message.answer(text)

@dp.message(Command("ping"))
async def ping(message: Message):
    text = """
🏓 BOT STATUS

⚙️ System: Active
🤖 Bot: Working
📡 Connection: OK
"""
    await message.answer(text)

@dp.message(F.text == "📊 Navbat")
@dp.message(Command("navbat"))
async def navbat(message: Message):
    await move_past_students_to_history()
    await reset_rotation_if_empty()
    
    student = await get_current_student()
    if not student:
        await smart_send(message, "Ro'yxat bo'sh.", 180)
        return

    months = ["yanvar","fevral","mart","aprel","may","iyun",
              "iyul","avgust","sentabr","oktabr","noyabr","dekabr"]
    today = datetime.now(UZ_TZ).date()
    next_date = student["shanbalik_date"]
    days_left = (next_date - today).days
    formatted_date = f"{next_date.day}-{months[next_date.month-1]} {next_date.year}"

    text = "━━━━━━━━━━━━━━━━━━\n"
    text += "📊 NAVBAT\n"
    text += "━━━━━━━━━━━━━━━━━━\n\n"
    text += f"👤 {student['name']:<18}\n"
    text += f"📅 {formatted_date:<18}\n"
    text += f"⏳ {days_left} kun qoldi\n"
    text += "\n━━━━━━━━━━━━━━━━━━"

    await smart_send(message, f"<pre>{text}</pre>", 180)

@dp.message(F.text == "📋 Ro‘yxat")
@dp.message(Command("royxat"))
async def royxat(message: Message):
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT name, shanbalik_date FROM students ORDER BY position")

    if not rows:
        await smart_send(message, "Ro'yxat bo'sh.", 300)
        return

    text = "━━━━━━━━━━━━━━━━━━\n📋 RO'YXAT\n━━━━━━━━━━━━━━━━━━\n\n"
    months = ["yanvar","fevral","mart","aprel","may","iyun",
              "iyul","avgust","sentabr","oktabr","noyabr","dekabr"]

    for i, r in enumerate(rows, start=1):
        date = r["shanbalik_date"]
        formatted_date = f"{date.day}-{months[date.month-1]} {date.year}"
        text += f"{i:>2}. {r['name']:<18} {formatted_date}\n"

    text += "\n━━━━━━━━━━━━━━━━━━"
    await smart_send(message, f"<pre>{text}</pre>", 300)

@dp.message(F.text == "📜 Tarix")
@dp.message(Command("tarix"))
async def tarix(message: Message):
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT name, shanbalik_date FROM history ORDER BY id ASC LIMIT 10"
        )

    if not rows:
        await smart_send(message, "Tarix bo'sh.", 300)
        return

    text = "━━━━━━━━━━━━━━━━━━\n📜 TARIX\n━━━━━━━━━━━━━━━━━━\n\n"
    months = ["yanvar","fevral","mart","aprel","may","iyun",
              "iyul","avgust","sentabr","oktabr","noyabr","dekabr"]

    for i, r in enumerate(rows, start=1):
        date = r["shanbalik_date"]
        formatted_date = f"{date.day}-{months[date.month-1]} {date.year}"
        text += f"{i:>2}. {r['name']:<18} {formatted_date}\n"

    text += "\n━━━━━━━━━━━━━━━━━━"
    await smart_send(message, f"<pre>{text}</pre>", 300)

@dp.message(F.text == "➕ O‘quvchi qo‘shish")
async def ask_student(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer("Ismini yuboring (private tavsiya qilinadi):")

@dp.message(
    F.chat.type == "private",
    F.text,
    ~F.text.startswith("/"),
    ~F.text.in_(["📊 Navbat", "📋 Ro‘yxat", "📜 Tarix", "➕ O‘quvchi qo‘shish"])
)
async def catch_private(message: Message):
    # Tug'ilgan kun saqlash
    try:
        birth_date = datetime.strptime(message.text, "%Y-%m-%d").date()
        async with db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO birthdays (user_id, name, birth_date)
                VALUES ($1, $2, $3)
                ON CONFLICT (user_id) DO NOTHING
            """, message.from_user.id, message.from_user.full_name, birth_date)
        await message.answer("🎂 Tug'ilgan kun saqlandi!")
        return
    except:
        pass

    # O'quvchi qo'shish
    if message.from_user.id in ADMIN_IDS:
        async with db_pool.acquire() as conn:
            count = await conn.fetchval("SELECT COUNT(*) FROM students")
            today = datetime.now(UZ_TZ).date()
            next_date = today + timedelta(days=count)
            await conn.execute(
                "INSERT INTO students (name, position, shanbalik_date) VALUES ($1, $2, $3) ON CONFLICT (name) DO NOTHING",
                message.text, count + 1, next_date
            )
        await message.answer("✅ Qo'shildi")

# ================= STARTUP =================
@app.on_event("startup")
async def startup():
    global db_pool
    
    try:
        # Komandalarni o'rnatish
        commands = [
            BotCommand(command="start", description="Botni ishga tushirish"),
            BotCommand(command="navbat", description="Hozirgi navbat"),
            BotCommand(command="royxat", description="Ro'yxat"),
            BotCommand(command="tarix", description="Tarix"),
            BotCommand(command="about", description="Bot haqida"),
            BotCommand(command="id", description="ID ni ko'rish"),
            BotCommand(command="ping", description="Bot holati")
        ]
        await bot.set_my_commands(commands)
        
        # Database ulanishi
        print(f"🔄 Database ga ulanish: {DATABASE_URL[:50]}...")
        
        # Maxsus parametrlar bilan ulanish
        db_pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=1,
            max_size=10,
            command_timeout=60,
            max_queries=50000,
            max_inactive_connection_lifetime=300
        )
        
        # Test query
        async with db_pool.acquire() as conn:
            await conn.execute("SELECT 1")
            print("✅ Database test query muvaffaqiyatli!")
        
        await init_db()
        print("✅ Database jadvallari yaratildi!")
        
        # Webhook
        await bot.delete_webhook(drop_pending_updates=True)
        await bot.set_webhook(WEBHOOK_URL)
        print(f"✅ Webhook sozlandi: {WEBHOOK_URL}")
        
        # SCHEDULER (AVTOMATIK ESLATMALAR)
        scheduler.add_job(monthly_reminder, "cron", day=1, hour=9, minute=0)
        scheduler.add_job(today_reminder, "cron", hour=7, minute=0)
        scheduler.add_job(friday_greeting, "cron", day_of_week="fri", hour=9, minute=0)
        scheduler.start()
        print("✅ Scheduler ishga tushdi!")
        
        print("✅ Bot ishga tushdi! AIogram 3.4.1")
        
    except Exception as e:
        print(f"❌ XATOLIK: {e}")
        print(f"❌ Xatolik turi: {type(e)}")
        import traceback
        traceback.print_exc()
        # Yangi a'zo kirganda hech narsa qilma
@dp.message()
async def handle_new_members(message: Message):
    if message.new_chat_members:
        # "X guruhga qo'shildi" xabarini o'chirish
        try:
            await message.delete()
        except:
            pass
        return
# ================= WEBHOOK =================
@app.post("/webhook")
async def webhook(request: Request):
    try:
        data = await request.json()
        update = types.Update(**data)
        await dp.feed_update(bot=bot, update=update)
        return JSONResponse({"ok": True})
    except Exception as e:
        print(f"Webhook xatolik: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.on_event("shutdown")
async def shutdown():
    await bot.session.close()
    if db_pool:
        await db_pool.close()

# ================= RUN =================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)