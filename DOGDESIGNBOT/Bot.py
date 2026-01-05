import subprocess
import sys
import asyncio
import sqlite3
from datetime import datetime, timedelta
import random

# ==========================
# Установка pytz если нет
# ==========================
try:
    import pytz
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pytz"])
    import pytz

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ================= CONFIG =================
TOKEN = "8376239597:AAHYeacPDfZDso4h3RD07vDYNTj9w9dg3wY"  # <-- Замените на рабочий токен
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

# ================= UTILS =================
def get_user(uid, username=""):
    sql.execute("SELECT id FROM users WHERE id=?", (uid,))
    if not sql.fetchone():
        sql.execute("INSERT INTO users(id, username) VALUES (?,?)", (uid, username))
        db.commit()

def tech_on():
    return sql.execute("SELECT tech FROM settings").fetchone()[0] == 1

def main_kb(is_admin=False):
    kb = [
        [InlineKeyboardButton("🖱 Клик", callback_data="click")],
        [InlineKeyboardButton("👤 Профиль", callback_data="profile"),
         InlineKeyboardButton("🏆 Рейтинг", callback_data="top")],
        [InlineKeyboardButton("🛒 Магазин", callback_data="shop")]
    ]
    if is_admin:
        kb.append([InlineKeyboardButton("⚙ Админ", callback_data="admin")])
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
    user = sql.execute("SELECT click, banned FROM users WHERE id=?", (uid,)).fetchone()
    if user[1]:
        return await call.answer("🚫 Вы забанены", show_alert=True)
    if tech_on() and uid not in ADMIN_IDS:
        return await call.answer("🛠 Технический перерыв", show_alert=True)
    sql.execute("UPDATE users SET points = points + ? WHERE id=?", (user[0], uid))
    db.commit()
    await call.answer(f"+{user[0]} очков")

# ================= PROFILE =================
@dp.callback_query(F.data == "profile")
async def profile(call: types.CallbackQuery):
    user = sql.execute("SELECT points, click, premium FROM users WHERE id=?", (call.from_user.id,)).fetchone()
    await call.message.edit_text(
        f"👤 Профиль\n💰 Очки: {user[0]}\n🖱 Клик: {user[1]}\n⭐ Премиум: {'Да' if user[2] else 'Нет'}",
        reply_markup=main_kb(call.from_user.id in ADMIN_IDS)
    )
    await call.answer()

# ================= SHOP =================
@dp.callback_query(F.data == "shop")
async def shop(call: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("⭐ Премиум — 5000", callback_data="buy_prem")],
        [InlineKeyboardButton("🔥 Ультра — 50000", callback_data="buy_ultra")],
        [InlineKeyboardButton("⬆ Улучшить клик — 1000", callback_data="upgrade_click")],
        [InlineKeyboardButton("⬅ Назад", callback_data="back")]
    ])
    await call.message.edit_text("🛒 Магазин", reply_markup=kb)
    await call.answer()

@dp.callback_query(F.data == "buy_prem")
async def buy_prem(call: types.CallbackQuery):
    uid = call.from_user.id
    points = sql.execute("SELECT points FROM users WHERE id=?", (uid,)).fetchone()[0]
    if points < 5000:
        return await call.answer("❌ Недостаточно очков", show_alert=True)
    sql.execute("UPDATE users SET points=points-5000, click=50, premium=1 WHERE id=?", (uid,))
    db.commit()
    await call.answer("⭐ Премиум активирован!", show_alert=True)

@dp.callback_query(F.data == "buy_ultra")
async def buy_ultra(call: types.CallbackQuery):
    uid = call.from_user.id
    points = sql.execute("SELECT points FROM users WHERE id=?", (uid,)).fetchone()[0]
    if points < 50000:
        return await call.answer("❌ Недостаточно очков", show_alert=True)
    sql.execute("UPDATE users SET points=points-50000, click=250, premium=2 WHERE id=?", (uid,))
    db.commit()
    await call.answer("🔥 Ультра активирован!", show_alert=True)

@dp.callback_query(F.data == "upgrade_click")
async def upgrade_click(call: types.CallbackQuery):
    uid = call.from_user.id
    points = sql.execute("SELECT points, click FROM users WHERE id=?", (uid,)).fetchone()
    if points[0] < 1000:
        return await call.answer("❌ Недостаточно очков", show_alert=True)
    sql.execute("UPDATE users SET points=points-1000, click=click+1 WHERE id=?", (uid,))
    db.commit()
    await call.answer("🖱 Клик улучшен на +1!", show_alert=True)

@dp.callback_query(F.data == "back")
async def back(call: types.CallbackQuery):
    await call.message.edit_text("Главное меню", reply_markup=main_kb(call.from_user.id in ADMIN_IDS))
    await call.answer()

# ================= ADMIN =================
@dp.callback_query(F.data == "admin")
async def admin_menu(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return await call.answer("🚫 Нет доступа", show_alert=True)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("➕ Очки", callback_data="a_points")],
        [InlineKeyboardButton("⭐ Премиум", callback_data="a_prem")],
        [InlineKeyboardButton("🚫 Бан", callback_data="a_ban")],
        [InlineKeyboardButton("🛠 Техперерыв", callback_data="a_tech")],
        [InlineKeyboardButton("📢 Рассылка в канал", callback_data="a_channel")]
    ])
    await call.message.edit_text("⚙ Админ меню", reply_markup=kb)
    await call.answer()

# ================= РЕЙТИНГ =================
@dp.callback_query(F.data == "top")
async def top_list(call: types.CallbackQuery):
    users = sql.execute("SELECT id, points FROM users ORDER BY points DESC LIMIT 10").fetchall()
    text = "🏆 Рейтинг:\n"
    for i, u in enumerate(users, 1):
        text += f"{i}. ID:{u[0]} — {u[1]} очков\n"
    await call.message.edit_text(text, reply_markup=main_kb(call.from_user.id in ADMIN_IDS))
    await call.answer()

# ================= DAILY TOP =================
async def daily_top():
    while True:
        now = datetime.now(MSK)
        target = now.replace(hour=0, minute=0, second=0) + timedelta(days=1)
        await asyncio.sleep((target - now).total_seconds())
        top = sql.execute("SELECT id FROM users ORDER BY points DESC LIMIT 1").fetchone()
        if top:
            sql.execute("UPDATE users SET points = points + 1000 WHERE id=?", (top[0],))
            db.commit()
            await bot.send_message(CHANNEL_ID, f"🏆 Топ-1 дня получил 1000 очков!\nID: {top[0]}")

# ================= ADMIN COMMANDS =================
@dp.message(Command("give"))
async def give(msg: types.Message):
    if msg.from_user.id not in ADMIN_IDS:
        return
    try:
        _, uid, amount = msg.text.split()
        uid = int(uid)
        amount = int(amount)
        sql.execute("UPDATE users SET points=points+? WHERE id=?", (amount, uid))
        db.commit()
        await msg.reply(f"✅ Выдано {amount} очков пользователю {uid}")
    except:
        await msg.reply("❌ Использование: /give <id> <кол-во>")

@dp.message(Command("premium"))
async def premium(msg: types.Message):
    if msg.from_user.id not in ADMIN_IDS:
        return
    try:
        _, uid, kind = msg.text.split()
        uid = int(uid)
        if kind.lower() == "prem":
            sql.execute("UPDATE users SET premium=1, click=50 WHERE id=?", (uid,))
        elif kind.lower() == "ultra":
            sql.execute("UPDATE users SET premium=2, click=250 WHERE id=?", (uid,))
        else:
            return await msg.reply("❌ Тип премиума: prem / ultra")
        db.commit()
        await msg.reply(f"✅ Премиум {kind} выдан пользователю {uid}")
    except:
        await msg.reply("❌ Использование: /premium <id> <prem/ultra>")

@dp.message(Command("ban"))
async def ban(msg: types.Message):
    if msg.from_user.id not in ADMIN_IDS:
        return
    try:
        _, uid = msg.text.split()
        uid = int(uid)
        sql.execute("UPDATE users SET banned=1 WHERE id=?", (uid,))
        db.commit()
        await msg.reply(f"🚫 Пользователь {uid} забанен")
    except:
        await msg.reply("❌ Использование: /ban <id>")

@dp.message(Command("unban"))
async def unban(msg: types.Message):
    if msg.from_user.id not in ADMIN_IDS:
        return
    try:
        _, uid = msg.text.split()
        uid = int(uid)
        sql.execute("UPDATE users SET banned=0 WHERE id=?", (uid,))
        db.commit()
        await msg.reply(f"✅ Пользователь {uid} разбанен")
    except:
        await msg.reply("❌ Использование: /unban <id>")

@dp.message(Command("tech"))
async def tech(msg: types.Message):
    if msg.from_user.id not in ADMIN_IDS:
        return
    try:
        _, state = msg.text.split()
        state = state.lower()
        if state == "on":
            sql.execute("UPDATE settings SET tech=1 WHERE id=1")
            db.commit()
            await msg.reply("🛠 Технический перерыв включен")
        elif state == "off":
            sql.execute("UPDATE settings SET tech=0 WHERE id=1")
            db.commit()
            await msg.reply("🛠 Технический перерыв выключен")
        else:
            await msg.reply("❌ Использование: /tech on/off")
    except:
        await msg.reply("❌ Использование: /tech on/off")

@dp.message(Command("broadcast"))
async def broadcast(msg: types.Message):
    if msg.from_user.id not in ADMIN_IDS:
        return
    text = msg.get_args()
    if not text:
        return await msg.reply("❌ Использование: /broadcast <текст>")
    await bot.send_message(CHANNEL_ID, text)
    await msg.reply("✅ Рассылка отправлена в канал")

# ================= MAIN =================
async def main():
    asyncio.create_task(daily_top())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
