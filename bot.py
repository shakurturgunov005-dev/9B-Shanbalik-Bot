import asyncio
import os
import asyncpg
import pytz
import random
import aiohttp
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types, F
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    BotCommand, ReplyKeyboardRemove
)
from aiogram.filters import Command, CommandStart
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import uvicorn

# ================= CONFIG =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
DATABASE_URL = os.getenv("DATABASE_URL")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")

if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

print(f"📦 Database URL: {DATABASE_URL[:30]}...")

GROUP_ID = -1003557503048
ADMIN_IDS = [6042457335]

UZ_TZ = pytz.timezone("Asia/Tashkent")

storage = MemoryStorage()
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=storage)
app = FastAPI()
scheduler = AsyncIOScheduler(timezone=UZ_TZ)

db_pool = None

MONTHS = ["yanvar ","fevral ","mart   ","aprel  ","may    ","iyun   ",
          "iyul   ","avgust ","sentabr","oktabr ","noyabr ","dekabr "]

# ================= TILAKLAR =================
morning_wishes = [
    "🤲 Alloh barchangizga bugungi kunni muborak va barakali qilsin!",
    "☀️ Bismillah bilan boshlangan kun doim xayrli bo'ladi!",
    "📿 Har kuni Allohni zikr qiling — qalblar faqat Allohni zikr qilish bilan xotirjam bo'ladi!",
    "🌿 Bugun ham solih amal qiling — har bir yaxshi ish sadaqadir!",
    "🤲 Alloh ilmingizni, axloqingizni va imoningizni ziyoda qilsin!",
    "☀️ Sabahul xayr! Bugungi kunni ibodат va ilm bilan bezang!",
    "🕌 Namozni o'z vaqtida o'qing — u eng yaxshi amallardan biridir!",
    "📚 Ilm izlash — har bir musulmonga farzdir. Bugun ham o'rganing!",
    "🌸 Alloh sizga sabr, shukr va sog'liq bersin!",
    "⭐ Ota-onangizga mehr ko'rsating — bu eng afzal ibodatlardan biridir!",
    "🤲 Tong namozini o'qib, kunni xayrli boshlang!",
    "🌙 Alloh barchangizni dunyо va oxiratda baxtli qilsin!",
]

# ================= OB-HAVO EMOJI =================
def get_weather_emoji(description):
    desc = description.lower()
    if "clear" in desc:
        return "☀️"
    elif "cloud" in desc:
        return "⛅"
    elif "rain" in desc:
        return "🌧️"
    elif "snow" in desc:
        return "❄️"
    elif "thunder" in desc:
        return "⛈️"
    elif "mist" in desc or "fog" in desc or "haze" in desc:
        return "🌫️"
    elif "wind" in desc:
        return "💨"
    else:
        return "🌤️"

def get_wind_direction(deg):
    directions = ["Shimol", "Shimol-Sharq", "Sharq", "Janub-Sharq",
                  "Janub", "Janub-G'arb", "G'arb", "Shimol-G'arb"]
    idx = round(deg / 45) % 8
    return directions[idx]

# ================= OB-HAVO FUNKSIYASI =================
async def morning_weather():
    try:
        url = (
            f"https://api.openweathermap.org/data/2.5/weather"
            f"?q=Namangan,UZ"
            f"&appid={WEATHER_API_KEY}"
            f"&units=metric"
            f"&lang=en"
        )
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.json()

        temp = round(data["main"]["temp"])
        feels_like = round(data["main"]["feels_like"])
        humidity = data["main"]["humidity"]
        wind_speed = round(data["wind"]["speed"])
        wind_deg = data["wind"].get("deg", 0)
        description = data["weather"][0]["description"]
        emoji = get_weather_emoji(description)
        wind_dir = get_wind_direction(wind_deg)

        desc_map = {
            "clear sky": "Ochiq osmon",
            "few clouds": "Ozgina bulut",
            "scattered clouds": "Bulutli",
            "broken clouds": "Ko'p bulutli",
            "overcast clouds": "Quyuq bulutli",
            "light rain": "Yengil yomg'ir",
            "moderate rain": "O'rtacha yomg'ir",
            "heavy intensity rain": "Kuchli yomg'ir",
            "thunderstorm": "Momaqaldiroq",
            "snow": "Qor",
            "mist": "Tuman",
            "fog": "Qalin tuman",
            "haze": "Tutun",
        }
        desc_uz = desc_map.get(description, description.capitalize())
        wish = random.choice(morning_wishes)
        today = datetime.now(UZ_TZ)
        is_friday = today.weekday() == 4  # 4 = Juma

        # Juma tabrigi
        if is_friday:
            today_date = today.date()
            if RAMAZON_START <= today_date <= RAMAZON_END:
                friday_text = random.choice(ramadan_friday_messages)
            else:
                friday_text = random.choice(normal_friday_messages)
        else:
            friday_text = None

        text = (
            f"🌅 Xayrli tong, Do'stlarim!\n"
            f"📅 {today.strftime('%d.%m.%Y')} | {today.strftime('%H:%M')}\n\n"
            f"🏙 Namangan ob-havosi:\n"
            f"{'━'*20}\n"
            f"{emoji} {desc_uz}\n"
            f"🌡 Harorat: {temp}°C (his: {feels_like}°C)\n"
            f"💧 Namlik: {humidity}%\n"
            f"💨 Shamol: {wind_speed} m/s, {wind_dir}\n"
            f"{'━'*20}\n\n"
            f"{wish}"
        )

        if friday_text:
            text += f"\n\n{'━'*20}\n{friday_text}"

        await bot.send_message(chat_id=GROUP_ID, text=text)

    except Exception as e:
        print(f"❌ Ob-havo xatolik: {e}")
        today = datetime.now(UZ_TZ)
        wish = random.choice(morning_wishes)
        text = (
            f"🌅 Xayrli tong, Do'stlarim!\n"
            f"📅 {today.strftime('%d.%m.%Y')}\n\n"
            f"{wish}"
        )
        await bot.send_message(chat_id=GROUP_ID, text=text)
# ================= FSM STATES =================
class AddStudent(StatesGroup):
    waiting_for_name = State()
    waiting_for_date = State()

# ================= KEYBOARDS =================
def main_menu_keyboard(is_admin=False):
    buttons = [
        [InlineKeyboardButton(text="📊 Navbat", callback_data="navbat")],
        [InlineKeyboardButton(text="📋 Ro'yxat", callback_data="royxat")],
        [InlineKeyboardButton(text="📜 Tarix", callback_data="tarix")],
    ]
    if is_admin:
        buttons.append([InlineKeyboardButton(text="⚙️ Admin panel", callback_data="admin_panel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def admin_panel_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ O'quvchi qo'shish", callback_data="add_student")],
        [InlineKeyboardButton(text="➖ O'quvchi o'chirish", callback_data="remove_student")],
        [InlineKeyboardButton(text="📊 O'quvchilar soni", callback_data="student_count")],
        [InlineKeyboardButton(text="🗑 Tarixni tozalash", callback_data="clear_history")],
        [InlineKeyboardButton(text="◀️ Orqaga", callback_data="back_main")],
    ])

def back_button(callback_data="back_main"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Orqaga", callback_data=callback_data)]
    ])

def confirm_keyboard(action):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Ha", callback_data=f"confirm_{action}"),
            InlineKeyboardButton(text="❌ Yo'q", callback_data="back_admin"),
        ]
    ])

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

# ================= UTIL FUNCTIONS =================
def format_date(date):
    day = str(date.day).zfill(2)
    month = MONTHS[date.month - 1]
    return f"{day}-{month} {date.year}"

async def move_past_students_to_history():
    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO history (name, shanbalik_date)
            SELECT name, shanbalik_date FROM students
            WHERE shanbalik_date < CURRENT_DATE
        """)
        await conn.execute("DELETE FROM students WHERE shanbalik_date < CURRENT_DATE")

async def get_current_student():
    async with db_pool.acquire() as conn:
        student = await conn.fetchrow("""
            SELECT * FROM students
            WHERE shanbalik_date >= CURRENT_DATE
            ORDER BY shanbalik_date ASC LIMIT 1
        """)
        if not student:
            student = await conn.fetchrow("""
                SELECT * FROM students ORDER BY shanbalik_date ASC LIMIT 1
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

# ================= TEXT HELPERS =================
def get_main_text(name, is_admin):
    role = "ADMIN 👑" if is_admin else "USER 👤"
    return (
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📊 SHANBALIK 2026\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"Assalomu alaykum, {name} 👋\n"
        f"Access Level: {role}\n"
        f"System Status: 🟢 Active\n"
        f"━━━━━━━━━━━━━━━━━━"
    )

async def get_navbat_text():
    await move_past_students_to_history()
    await reset_rotation_if_empty()
    student = await get_current_student()
    if not student:
        return "📭 Ro'yxat bo'sh."
    today = datetime.now(UZ_TZ).date()
    next_date = student["shanbalik_date"]
    days_left = (next_date - today).days
    return (
        "━━━━━━━━━━━━━━━━━━\n"
        "📊 NAVBAT\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 {student['name']}\n"
        f"📅 {format_date(next_date)}\n"
        f"⏳ {days_left} kun qoldi\n"
        "\n━━━━━━━━━━━━━━━━━━"
    )

async def get_royxat_text():
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT name, shanbalik_date FROM students ORDER BY position")
    if not rows:
        return "📭 Ro'yxat bo'sh."
    text = "━━━━━━━━━━━━━━━━━━\n📋 RO'YXAT\n━━━━━━━━━━━━━━━━━━\n\n"
    for i, r in enumerate(rows, start=1):
        name = r['name'][:14].ljust(14)
        date = format_date(r['shanbalik_date'])
        text += f"{i:>2}. {name} {date}\n"
    text += "\n━━━━━━━━━━━━━━━━━━"
    return text

async def get_tarix_text():
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT name, shanbalik_date FROM history ORDER BY id ASC LIMIT 10")
    if not rows:
        return "📭 Tarix bo'sh."
    text = "━━━━━━━━━━━━━━━━━━\n📜 TARIX\n━━━━━━━━━━━━━━━━━━\n\n"
    for i, r in enumerate(rows, start=1):
        name = r['name'][:14].ljust(14)
        date = format_date(r['shanbalik_date'])
        text += f"{i:>2}. {name} {date}\n"
    text += "\n━━━━━━━━━━━━━━━━━━"
    return text

# ================= COMMAND HANDLERS =================
@dp.message(CommandStart())
async def start_handler(message: Message, state: FSMContext):
    await state.clear()
    is_admin = message.from_user.id in ADMIN_IDS
    text = get_main_text(message.from_user.full_name, is_admin)
    await message.answer("✅", reply_markup=ReplyKeyboardRemove())
    await message.answer(f"<pre>{text}</pre>", parse_mode="HTML",
                         reply_markup=main_menu_keyboard(is_admin))

@dp.message(Command("ping"))
async def ping(message: Message):
    text = (
        "━━━━━━━━━━━━━━━━━━\n"
        "🏓 BOT STATUS\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "⚙️ System: Active\n"
        "🤖 Bot: Working\n"
        "📡 Connection: OK\n"
        "━━━━━━━━━━━━━━━━━━"
    )
    await message.answer(f"<pre>{text}</pre>", parse_mode="HTML")

@dp.message(Command("id"))
async def get_id(message: Message):
    text = (
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🆔 ID MA'LUMOTLARI\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 Sizning ID: {message.from_user.id}\n"
        f"💬 Chat ID: {message.chat.id}\n"
        f"━━━━━━━━━━━━━━━━━━"
    )
    await message.answer(f"<pre>{text}</pre>", parse_mode="HTML")

@dp.message(Command("about"))
async def about(message: Message):
    text = (
        "━━━━━━━━━━━━━━━━━━\n"
        "🤖 BOT HAQIDA\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "📌 Shanbalik navbat bot\n"
        "📅 Navbatlarni avtomatik yuritadi\n"
        "⏰ Eslatmalar yuboradi\n"
        "🌤 Har kuni ob-havo ma'lumoti\n\n"
        "👨‍💻 Developer: Shukurullo\n"
        "📅 2026\n"
        "⚙️ Version: 6.1\n"
        "━━━━━━━━━━━━━━━━━━"
    )
    await message.answer(f"<pre>{text}</pre>", parse_mode="HTML")

@dp.message(Command("clear"))
async def clear_keyboard(message: Message):
    if message.chat.type == "private":
        return
    await message.answer("✅ Klaviatura tozalandi!", reply_markup=ReplyKeyboardRemove())

# ================= MAIN MENU CALLBACKS =================
@dp.callback_query(F.data == "navbat")
async def cb_navbat(callback: CallbackQuery):
    text = await get_navbat_text()
    await callback.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                     reply_markup=back_button())
    await callback.answer()

@dp.callback_query(F.data == "royxat")
async def cb_royxat(callback: CallbackQuery):
    text = await get_royxat_text()
    await callback.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                     reply_markup=back_button())
    await callback.answer()

@dp.callback_query(F.data == "tarix")
async def cb_tarix(callback: CallbackQuery):
    text = await get_tarix_text()
    await callback.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                     reply_markup=back_button())
    await callback.answer()

@dp.callback_query(F.data == "back_main")
async def cb_back_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    is_admin = callback.from_user.id in ADMIN_IDS
    text = get_main_text(callback.from_user.full_name, is_admin)
    await callback.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                     reply_markup=main_menu_keyboard(is_admin))
    await callback.answer()

# ================= ADMIN PANEL =================
@dp.callback_query(F.data == "admin_panel")
async def cb_admin_panel(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Ruxsat yo'q!", show_alert=True)
        return
    text = (
        "━━━━━━━━━━━━━━━━━━\n"
        "⚙️ ADMIN PANEL\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "Quyidagi amallardan birini tanlang:"
    )
    await callback.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                     reply_markup=admin_panel_keyboard())
    await callback.answer()

@dp.callback_query(F.data == "back_admin")
async def cb_back_admin(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Ruxsat yo'q!", show_alert=True)
        return
    text = (
        "━━━━━━━━━━━━━━━━━━\n"
        "⚙️ ADMIN PANEL\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "Quyidagi amallardan birini tanlang:"
    )
    await callback.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                     reply_markup=admin_panel_keyboard())
    await callback.answer()

# ================= ADD STUDENT =================
@dp.callback_query(F.data == "add_student")
async def cb_add_student(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Ruxsat yo'q!", show_alert=True)
        return
    await state.set_state(AddStudent.waiting_for_name)
    await state.update_data(message_id=callback.message.message_id,
                             chat_id=callback.message.chat.id)
    text = (
        "━━━━━━━━━━━━━━━━━━\n"
        "➕ O'QUVCHI QO'SHISH\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "👤 Ism familyani yozing:\n"
        "(Masalan: Aliyev Ali)"
    )
    await callback.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                     reply_markup=back_button("back_admin"))
    await callback.answer()

@dp.message(AddStudent.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    data = await state.get_data()
    await state.update_data(name=message.text)
    await state.set_state(AddStudent.waiting_for_date)
    try:
        await message.delete()
    except:
        pass
    text = (
        "━━━━━━━━━━━━━━━━━━\n"
        "➕ O'QUVCHI QO'SHISH\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 Ism: {message.text}\n\n"
        "📅 Shanbalik sanasini yozing:\n"
        "(Masalan: 15.06.2026)"
    )
    try:
        await bot.edit_message_text(
            f"<pre>{text}</pre>",
            chat_id=data["chat_id"],
            message_id=data["message_id"],
            parse_mode="HTML",
            reply_markup=back_button("back_admin")
        )
    except:
        sent = await message.answer(f"<pre>{text}</pre>", parse_mode="HTML",
                                    reply_markup=back_button("back_admin"))
        await state.update_data(message_id=sent.message_id, chat_id=message.chat.id)

@dp.message(AddStudent.waiting_for_date)
async def process_date(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    data = await state.get_data()
    try:
        await message.delete()
    except:
        pass
    try:
        date = datetime.strptime(message.text.strip(), "%d.%m.%Y").date()
    except ValueError:
        text = (
            "━━━━━━━━━━━━━━━━━━\n"
            "⚠️ XATO FORMAT\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "Sana to'g'ri formatda emas!\n"
            "📅 To'g'ri format: 15.06.2026\n\n"
            "Qaytadan yozing:"
        )
        try:
            await bot.edit_message_text(
                f"<pre>{text}</pre>",
                chat_id=data["chat_id"],
                message_id=data["message_id"],
                parse_mode="HTML",
                reply_markup=back_button("back_admin")
            )
        except:
            pass
        return

    name = data["name"]
    async with db_pool.acquire() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM students")
        await conn.execute(
            "INSERT INTO students (name, position, shanbalik_date) VALUES ($1, $2, $3) ON CONFLICT (name) DO NOTHING",
            name, count + 1, date
        )
    await state.clear()
    text = (
        "━━━━━━━━━━━━━━━━━━\n"
        "✅ QO'SHILDI\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 {name}\n"
        f"📅 {format_date(date)}\n"
        "━━━━━━━━━━━━━━━━━━"
    )
    try:
        await bot.edit_message_text(
            f"<pre>{text}</pre>",
            chat_id=data["chat_id"],
            message_id=data["message_id"],
            parse_mode="HTML",
            reply_markup=back_button("back_admin")
        )
    except:
        await message.answer(f"<pre>{text}</pre>", parse_mode="HTML",
                             reply_markup=back_button("back_admin"))

# ================= REMOVE STUDENT =================
@dp.callback_query(F.data == "remove_student")
async def cb_remove_student(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Ruxsat yo'q!", show_alert=True)
        return
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT id, name, shanbalik_date FROM students ORDER BY position")
    if not rows:
        await callback.answer("📭 Ro'yxat bo'sh!", show_alert=True)
        return
    buttons = []
    for row in rows:
        buttons.append([InlineKeyboardButton(
            text=f"❌ {row['name']} — {format_date(row['shanbalik_date'])}",
            callback_data=f"del_{row['id']}"
        )])
    buttons.append([InlineKeyboardButton(text="◀️ Orqaga", callback_data="back_admin")])
    text = (
        "━━━━━━━━━━━━━━━━━━\n"
        "➖ O'QUVCHI O'CHIRISH\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "O'chirmoqchi bo'lgan o'quvchini tanlang:"
    )
    await callback.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                     reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await callback.answer()

@dp.callback_query(F.data.startswith("del_"))
async def cb_delete_student(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Ruxsat yo'q!", show_alert=True)
        return
    student_id = int(callback.data.replace("del_", ""))
    async with db_pool.acquire() as conn:
        student = await conn.fetchrow("SELECT name FROM students WHERE id = $1", student_id)
        await conn.execute("DELETE FROM students WHERE id = $1", student_id)
        await conn.execute("""
            WITH numbered AS (
                SELECT id, ROW_NUMBER() OVER (ORDER BY position) as new_pos FROM students
            )
            UPDATE students SET position = numbered.new_pos
            FROM numbered WHERE students.id = numbered.id
        """)
    name = student["name"] if student else "O'quvchi"
    text = (
        "━━━━━━━━━━━━━━━━━━\n"
        "✅ O'CHIRILDI\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 {name} ro'yxatdan o'chirildi.\n"
        "━━━━━━━━━━━━━━━━━━"
    )
    await callback.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                     reply_markup=back_button("back_admin"))
    await callback.answer()

# ================= STUDENT COUNT =================
@dp.callback_query(F.data == "student_count")
async def cb_student_count(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Ruxsat yo'q!", show_alert=True)
        return
    async with db_pool.acquire() as conn:
        students = await conn.fetchval("SELECT COUNT(*) FROM students")
        history = await conn.fetchval("SELECT COUNT(*) FROM history")
        next_student = await get_current_student()
    next_name = next_student['name'] if next_student else "Yo'q"
    text = (
        "━━━━━━━━━━━━━━━━━━\n"
        "📊 STATISTIKA\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 Jami o'quvchilar: {students}\n"
        f"📜 Tarixda: {history}\n"
        f"👤 Keyingi navbatchi: {next_name}\n"
        "━━━━━━━━━━━━━━━━━━"
    )
    await callback.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                     reply_markup=back_button("back_admin"))
    await callback.answer()

# ================= CLEAR HISTORY =================
@dp.callback_query(F.data == "clear_history")
async def cb_clear_history(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Ruxsat yo'q!", show_alert=True)
        return
    text = (
        "━━━━━━━━━━━━━━━━━━\n"
        "🗑 TARIXNI TOZALASH\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "⚠️ Haqiqatan tarixni tozalamoqchimisiz?"
    )
    await callback.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                     reply_markup=confirm_keyboard("clear_history"))
    await callback.answer()

@dp.callback_query(F.data == "confirm_clear_history")
async def cb_confirm_clear_history(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Ruxsat yo'q!", show_alert=True)
        return
    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM history")
    text = (
        "━━━━━━━━━━━━━━━━━━\n"
        "✅ TARIX TOZALANDI\n"
        "━━━━━━━━━━━━━━━━━━"
    )
    await callback.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                     reply_markup=back_button("back_admin"))
    await callback.answer()

# ================= REMINDER FUNCTIONS =================
async def one_day_before_reminder():
    student = await get_current_student()
    if not student:
        return
    today = datetime.now(UZ_TZ).date()
    shanbalik_date = student["shanbalik_date"]
    if (shanbalik_date - today).days == 1:
        text = (
            f"📢 Eslatma! 1 kun qoldi\n"
            f"Ertaga shanbalik:\n"
            f"👤 {student['name']}\n"
            f"📅 {format_date(shanbalik_date)}"
        )
        await bot.send_message(chat_id=GROUP_ID, text=text)

async def today_reminder():
    student = await get_current_student()
    if not student:
        return
    today = datetime.now(UZ_TZ).date()
    if student["shanbalik_date"] != today:
        return
    text = (
        f"📢 Bugun shanbalik:\n"
        f"👤 {student['name']}\n"
        f"📅 {format_date(today)}"
    )
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
    "🌙 Hayrli jumalar!\n\nBugun qilgan duolaringiz,\nniyatlaringiz ijobat bo'lsin."
]

async def friday_greeting():
    today = datetime.now(UZ_TZ).date()
    if RAMAZON_START <= today <= RAMAZON_END:
        text = random.choice(ramadan_friday_messages)
    else:
        text = random.choice(normal_friday_messages)
    await bot.send_message(chat_id=GROUP_ID, text=text)

# ================= CATCH ALL =================
@dp.message()
async def handle_all(message: Message):
    if message.new_chat_members:
        try:
            await message.delete()
        except:
            pass

# ================= STARTUP =================
@app.on_event("startup")
async def startup():
    global db_pool
    try:
        commands = [
            BotCommand(command="start", description="Botni ishga tushirish"),
            BotCommand(command="about", description="Bot haqida"),
            BotCommand(command="ping", description="Bot holati"),
            BotCommand(command="id", description="ID ni ko'rish"),
            BotCommand(command="clear", description="Klaviaturani tozalash"),
        ]
        await bot.set_my_commands(commands)

        print(f"🔄 Database ga ulanish: {DATABASE_URL[:50]}...")
        db_pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=1,
            max_size=10,
            command_timeout=60,
            max_queries=50000,
            max_inactive_connection_lifetime=300
        )
        async with db_pool.acquire() as conn:
            await conn.execute("SELECT 1")
            print("✅ Database test query muvaffaqiyatli!")

        await init_db()
        print("✅ Database jadvallari yaratildi!")

        await bot.delete_webhook(drop_pending_updates=True)
        await bot.set_webhook(WEBHOOK_URL)
        print(f"✅ Webhook sozlandi: {WEBHOOK_URL}")

        scheduler.add_job(morning_weather, "cron", hour=6, minute=0)
        scheduler.add_job(today_reminder, "cron", hour=7, minute=0)
        scheduler.add_job(one_day_before_reminder, "cron", hour=7, minute=0)
        scheduler.add_job(friday_greeting, "cron", day_of_week="fri", hour=9, minute=0)
        scheduler.start()
        print("✅ Scheduler ishga tushdi!")
        print("✅ Bot ishga tushdi! Version 6.1")

    except Exception as e:
        print(f"❌ XATOLIK: {e}")
        import traceback
        traceback.print_exc()

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
