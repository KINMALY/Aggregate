import asyncio
import sqlite3
import random
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

# ================= НАСТРОЙКИ =================
TOKEN = "ВАШ_ТОКЕН"
ADMIN_IDS = [7388659987]
CHANNEL_ID = 1003650699170  # твой канал

bot = Bot(TOKEN)
dp = Dispatcher()

# ================= БД =================
db = sqlite3.connect("bot.db")
sql = db.cursor()

# Таблица пользователей
sql.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    points INTEGER DEFAULT 0,
    premium TEXT DEFAULT 'none',
    click_boost INTEGER DEFAULT 1,
    banned INTEGER DEFAULT 0,
    last_daily TEXT DEFAULT 'never',
    last_top_reward TEXT DEFAULT 'never'
)
""")

# Таблица настроек
sql.execute("""
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
)
""")
sql.execute("INSERT OR IGNORE INTO settings VALUES ('tech', 'off')")
db.commit()

# ================= FSM =================
class AdminFSM(StatesGroup):
    give_points = State()
    give_premium = State()
    ban = State()
    unban = State()

# ================= УТИЛИТЫ =================
def get_user(uid, username):
    sql.execute("SELECT * FROM users WHERE user_id=?", (uid,))
    user = sql.fetchone()
    if not user:
        sql.execute(
            "INSERT INTO users (user_id, username) VALUES (?,?)",
            (uid, username)
        )
        db.commit()
        return get_user(uid, username)
    return user

def tech_enabled():
    sql.execute("SELECT value FROM settings WHERE key='tech'")
    return sql.fetchone()[0] == "on"

def get_all_user_ids():
    sql.execute("SELECT user_id FROM users")
    return [u[0] for u in sql.fetchall()]

# ================= КЛАВИАТУРЫ =================
def main_menu(admin=False):
    kb = InlineKeyboardBuilder()
    kb.button(text="⚡ Клик", callback_data="click")
    kb.button(text="👤 Профиль", callback_data="profile")
    kb.button(text="🏆 Рейтинг", callback_data="rating")
    kb.button(text="🛒 Магазин", callback_data="shop")
    kb.button(text="🎁 Бонус", callback_data="daily")
    if admin:
        kb.button(text="🛠 Админ", callback_data="admin")
    kb.adjust(2)
    return kb.as_markup()

def admin_menu():
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Очки", callback_data="a_points")
    kb.button(text="⭐ Премиум", callback_data="a_premium")
    kb.button(text="🚫 Бан", callback_data="a_ban")
    kb.button(text="✅ Разбан", callback_data="a_unban")
    kb.button(text="🛠 Техперерыв", callback_data="a_tech")
    kb.button(text="⬅ Назад", callback_data="back")
    kb.adjust(1)
    return kb.as_markup()

def shop_menu():
    kb = InlineKeyboardBuilder()
    kb.button(text="⭐ Премиум (5000)", callback_data="buy_premium")
    kb.button(text="💎 Ультра (50000)", callback_data="buy_ultra")
    kb.button(text="⚡ x2 клик (2000)", callback_data="boost_2")
    kb.button(text="⚡ x5 клик (8000)", callback_data="boost_5")
    kb.button(text="⬅ Назад", callback_data="back")
    kb.adjust(1)
    return kb.as_markup()

# ================= START =================
@dp.message(Command("start"))
async def start(msg: types.Message):
    user = get_user(msg.from_user.id, msg.from_user.username)
    if user[5]:
        await msg.answer("🚫 Вы заблокированы")
        return
    await msg.answer(
        "👋 Добро пожаловать в кликер!",
        reply_markup=main_menu(msg.from_user.id in ADMIN_IDS)
    )

# ================= CALLBACK =================
@dp.callback_query()
async def callbacks(call: types.CallbackQuery, state: FSMContext):
    uid = call.from_user.id
    user = get_user(uid, call.from_user.username)
    admin = uid in ADMIN_IDS
    data = call.data

    if user[5]:
        await call.answer("🚫 Вы заблокированы", show_alert=True)
        return
    if tech_enabled() and not admin:
        await call.answer("🛠 Технический перерыв", show_alert=True)
        return

    # ---------- КЛИК ----------
    if data == "click":
        gain = 250 if user[3] == "ultra" else 1
        gain *= user[4]
        sql.execute("UPDATE users SET points=points+? WHERE user_id=?", (gain, uid))
        db.commit()
        await call.answer(f"+{gain}")

    # ---------- ПРОФИЛЬ ----------
    elif data == "profile":
        await call.message.edit_text(
            f"👤 Профиль\nID: {uid}\nОчки: {user[2]}\nСтатус: {user[3]}\nМножитель: x{user[4]}",
            reply_markup=main_menu(admin)
        )

    # ---------- РЕЙТИНГ ----------
    elif data == "rating":
        sql.execute("SELECT username, points FROM users ORDER BY points DESC LIMIT 10")
        text = "🏆 ТОП-10\n\n"
        for i, u in enumerate(sql.fetchall(), 1):
            text += f"{i}. {u[0]} — {u[1]}\n"
        await call.message.edit_text(text, reply_markup=main_menu(admin))

    # ---------- ДНЕВНОЙ БОНУС ----------
    elif data == "daily":
        today = datetime.now().strftime("%Y-%m-%d")
        if user[6] == today:
            await call.answer("❌ Уже получали", show_alert=True)
            return
        reward_type = random.choice(["points","boost"])
        if reward_type=="points":
            reward = random.choice([500,1000,2000,5000])
            sql.execute("UPDATE users SET points=points+?, last_daily=? WHERE user_id=?",(reward,today,uid))
            await call.answer(f"🎁 +{reward} очков", show_alert=True)
        else:
            boost = random.choice([2,5])
            sql.execute("UPDATE users SET click_boost=?, last_daily=? WHERE user_id=?",(boost,today,uid))
            await call.answer(f"⚡ Улучшение x{boost}", show_alert=True)
        db.commit()

    # ---------- МАГАЗИН ----------
    elif data == "shop":
        await call.message.edit_text("🛒 Магазин", reply_markup=shop_menu())
    elif data == "buy_premium":
        if user[2]>=5000:
            sql.execute("UPDATE users SET points=points-5000,premium='premium' WHERE user_id=?",(uid,))
            db.commit()
            await call.answer("⭐ Премиум выдан")
        else:
            await call.answer("❌ Недостаточно очков", show_alert=True)
    elif data == "buy_ultra":
        if user[2]>=50000:
            sql.execute("UPDATE users SET points=points-50000,premium='ultra' WHERE user_id=?",(uid,))
            db.commit()
            await call.answer("💎 Ультра выдана")
        else:
            await call.answer("❌ Недостаточно очков", show_alert=True)
    elif data=="boost_2":
        sql.execute("UPDATE users SET click_boost=2 WHERE user_id=?",(uid,))
        db.commit()
        await call.answer("⚡ x2 активирован")
    elif data=="boost_5":
        sql.execute("UPDATE users SET click_boost=5 WHERE user_id=?",(uid,))
        db.commit()
        await call.answer("⚡ x5 активирован")

    # ---------- АДМИН ----------
    elif data=="admin" and admin:
        await call.message.edit_text("🛠 Админ меню", reply_markup=admin_menu())
    elif data=="a_points":
        await call.message.answer("ID СУММА")
        await state.set_state(AdminFSM.give_points)
    elif data=="a_premium":
        await call.message.answer("ID premium/ultra")
        await state.set_state(AdminFSM.give_premium)
    elif data=="a_ban":
        await call.message.answer("ID")
        await state.set_state(AdminFSM.ban)
    elif data=="a_unban":
        await call.message.answer("ID")
        await state.set_state(AdminFSM.unban)
    elif data=="a_tech":
        new="off" if tech_enabled() else "on"
        sql.execute("UPDATE settings SET value=? WHERE key='tech'",(new,))
        db.commit()
        text = "🛠 Техперерыв ВКЛЮЧЁН" if new=="on" else "✅ Техперерыв ЗАВЕРШЁН"
        try:
            await bot.send_message(CHANNEL_ID,text)
        except: pass
        await call.answer("Готово")
    elif data=="back":
        await call.message.edit_text("Главное меню", reply_markup=main_menu(admin))

# ================= FSM =================
@dp.message(AdminFSM.give_points)
async def give_points(msg: types.Message,state:FSMContext):
    uid,pts=map(int,msg.text.split())
    sql.execute("UPDATE users SET points=points+? WHERE user_id=?",(pts,uid))
    db.commit()
    await msg.answer("✅ Очки выданы")
    await state.clear()

@dp.message(AdminFSM.give_premium)
async def give_premium(msg: types.Message,state:FSMContext):
    uid,p=msg.text.split()
    sql.execute("UPDATE users SET premium=? WHERE user_id=?",(p,int(uid)))
    db.commit()
    await msg.answer("✅ Готово")
    await state.clear()

@dp.message(AdminFSM.ban)
async def ban(msg: types.Message,state:FSMContext):
    sql.execute("UPDATE users SET banned=1 WHERE user_id=?",(int(msg.text),))
    db.commit()
    await msg.answer("🚫 Забанен")
    await state.clear()

@dp.message(AdminFSM.unban)
async def unban(msg: types.Message,state:FSMContext):
    sql.execute("UPDATE users SET banned=0 WHERE user_id=?",(int(msg.text),))
    db.commit()
    await msg.answer("✅ Разбанен")
    await state.clear()

# ================= ТОП-1 рассылка каждый день МСК 00:00 =================
async def top1_daily():
    while True:
        now=datetime.utcnow()+timedelta(hours=3)
        next_midnight=(now+timedelta(days=1)).replace(hour=0,minute=0,second=0)
        await asyncio.sleep((next_midnight-now).total_seconds())
        sql.execute("SELECT user_id, last_top_reward FROM users ORDER BY points DESC LIMIT 1")
        top=sql.fetchone()
        if top:
            today=next_midnight.strftime("%Y-%m-%d")
            if top[1]!=today:
                sql.execute("UPDATE users SET points=points+1000,last_top_reward=? WHERE user_id=?",(today,top[0]))
                db.commit()
                try:
                    await bot.send_message(top[0],"🏆 Вы ТОП-1 сегодня!\n🎁 +1000 очков")
                    await bot.send_message(CHANNEL_ID,f"🏆 ТОП-1: {top[0]} получил 1000 очков!")
                except: pass

# ================= RUN =================
async def main():
    asyncio.create_task(top1_daily())
    await dp.start_polling(bot)

if __name__=="__main__":
    asyncio.run(main())
