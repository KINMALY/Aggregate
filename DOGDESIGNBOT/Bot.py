import asyncio
import sqlite3
from datetime import datetime, timedelta
import pytz
import random

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ================= CONFIG =================
TOKEN = "8376239597:AAHYeacPDfZDso4h3RD07vDYNTj9w9dg3wY"
ADMIN_IDS = [7388659987]
CHANNEL_ID = -1003650699170
MSK = pytz.timezone("Europe/Moscow")

# ================= DB =================
db = sqlite3.connect("database.db")
sql = db.cursor()

sql.execute("""
CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY,
    username TEXT,
    points INTEGER DEFAULT 0,
    click INTEGER DEFAULT 1,
    premium INTEGER DEFAULT 0,
    banned INTEGER DEFAULT 0,
    last_bonus TEXT
)
""")

sql.execute("""
CREATE TABLE IF NOT EXISTS settings(
    id INTEGER PRIMARY KEY,
    tech INTEGER DEFAULT 0
)
""")

sql.execute("INSERT OR IGNORE INTO settings(id, tech) VALUES (1,0)")
db.commit()

# ================= FSM =================
class AdminFSM(StatesGroup):
    target_id = State()
    amount = State()
    action = State()

# ================= UTILS =================
def get_user(uid, username=""):
    sql.execute("SELECT id FROM users WHERE id=?", (uid,))
    if not sql.fetchone():
        sql.execute(
            "INSERT INTO users(id, username) VALUES (?,?)",
            (uid, username)
        )
        db.commit()

def tech_on():
    return sql.execute("SELECT tech FROM settings").fetchone()[0] == 1

def main_kb(is_admin=False):
    kb = [
        [InlineKeyboardButton(text="🖱 Клик", callback_data="click")],
        [InlineKeyboardButton(text="👤 Профиль", callback_data="profile"),
         InlineKeyboardButton(text="🏆 Рейтинг", callback_data="top")],
        [InlineKeyboardButton(text="🛒 Магазин", callback_data="shop")]
    ]
    if is_admin:
        kb.append([InlineKeyboardButton(text="⚙ Админ", callback_data="admin")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

# ================= BOT =================
bot = Bot(TOKEN)
dp = Dispatcher()

# ================= START =================
@dp.message(Command("start"))
async def start(msg: types.Message):
    get_user(msg.from_user.id, msg.from_user.username or "")
    await msg.answer(
        "Добро пожаловать в Clicker Bot!",
        reply_markup=main_kb(msg.from_user.id in ADMIN_IDS)
    )

# ================= CLICK =================
@dp.callback_query(F.data == "click")
async def click(call: types.CallbackQuery):
    uid = call.from_user.id
    user = sql.execute(
        "SELECT click, banned FROM users WHERE id=?",
        (uid,)
    ).fetchone()

    if user[1]:
        return await call.answer("🚫 Вы забанены")

    if tech_on() and uid not in ADMIN_IDS:
        return await call.answer("🛠 Технический перерыв")

    sql.execute(
        "UPDATE users SET points = points + ? WHERE id=?",
        (user[0], uid)
    )
    db.commit()
    await call.answer(f"+{user[0]} очков")

# ================= PROFILE =================
@dp.callback_query(F.data == "profile")
async def profile(call: types.CallbackQuery):
    user = sql.execute(
        "SELECT points, click, premium FROM users WHERE id=?",
        (call.from_user.id,)
    ).fetchone()

    await call.message.edit_text(
        f"👤 Профиль\n"
        f"💰 Очки: {user[0]}\n"
        f"🖱 Клик: {user[1]}\n"
        f"⭐ Премиум: {'Да' if user[2] else 'Нет'}",
        reply_markup=main_kb(call.from_user.id in ADMIN_IDS)
    )

# ================= SHOP =================
@dp.callback_query(F.data == "shop")
async def shop(call: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("⭐ Премиум — 5000", callback_data="buy_prem")],
        [InlineKeyboardButton("🔥 Ультра — 50000", callback_data="buy_ultra")],
        [InlineKeyboardButton("⬅ Назад", callback_data="back")]
    ])
    await call.message.edit_text("🛒 Магазин", reply_markup=kb)

@dp.callback_query(F.data == "buy_prem")
async def buy_prem(call: types.CallbackQuery):
    uid = call.from_user.id
    pts = sql.execute("SELECT points FROM users WHERE id=?", (uid,)).fetchone()[0]
    if pts < 5000:
        return await call.answer("❌ Недостаточно очков")
    sql.execute(
        "UPDATE users SET points=points-5000, click=50, premium=1 WHERE id=?",
        (uid,)
    )
    db.commit()
    await call.answer("⭐ Премиум активирован!")

@dp.callback_query(F.data == "buy_ultra")
async def buy_ultra(call: types.CallbackQuery):
    uid = call.from_user.id
    pts = sql.execute("SELECT points FROM users WHERE id=?", (uid,)).fetchone()[0]
    if pts < 50000:
        return await call.answer("❌ Недостаточно очков")
    sql.execute(
        "UPDATE users SET points=points-50000, click=250, premium=2 WHERE id=?",
        (uid,)
    )
    db.commit()
    await call.answer("🔥 Ультра активирован!")

@dp.callback_query(F.data == "back")
async def back(call: types.CallbackQuery):
    await call.message.edit_text(
        "Главное меню",
        reply_markup=main_kb(call.from_user.id in ADMIN_IDS)
    )

# ================= ADMIN =================
@dp.callback_query(F.data == "admin")
async def admin(call: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("➕ Очки", callback_data="a_points")],
        [InlineKeyboardButton("⭐ Премиум", callback_data="a_prem")],
        [InlineKeyboardButton("🚫 Бан", callback_data="a_ban")],
        [InlineKeyboardButton("🛠 Техперерыв", callback_data="a_tech")]
    ])
    await call.message.edit_text("⚙ Админ меню", reply_markup=kb)

# ================= DAILY TOP =================
async def daily_top():
    while True:
        now = datetime.now(MSK)
        target = now.replace(hour=0, minute=0, second=0) + timedelta(days=1)
        await asyncio.sleep((target - now).total_seconds())

        top = sql.execute(
            "SELECT id FROM users ORDER BY points DESC LIMIT 1"
        ).fetchone()
        if top:
            sql.execute(
                "UPDATE users SET points = points + 1000 WHERE id=?",
                (top[0],)
            )
            db.commit()
            await bot.send_message(
                CHANNEL_ID,
                f"🏆 Топ-1 дня получил 1000 очков!\nID: {top[0]}"
            )

# ================= MAIN =================
async def main():
    asyncio.create_task(daily_top())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
