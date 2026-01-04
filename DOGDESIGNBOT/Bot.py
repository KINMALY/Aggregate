import sqlite3
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.utils.keyboard import InlineKeyboardBuilder

# ----------------- НАСТРОЙКИ -----------------
TOKEN = "8376239597:AAHYeacPDfZDso4h3RD07vDYNTj9w9dg3wY"  # твой токен
ADMIN_IDS = [7388659987]  # твой ID

bot = Bot(token=TOKEN)
dp = Dispatcher()

# ================== БАЗА ДАННЫХ ==================
conn = sqlite3.connect("clicker.db")
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    points INTEGER DEFAULT 0,
    premium TEXT DEFAULT 'none',
    clicks INTEGER DEFAULT 0
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS settings (
    name TEXT PRIMARY KEY,
    value TEXT
)
''')
conn.commit()

cursor.execute("INSERT OR IGNORE INTO settings (name, value) VALUES ('maintenance', 'off')")
conn.commit()

# ================== ХЕЛПЕРЫ ==================
def get_user(user_id, username):
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    if not user:
        cursor.execute("INSERT INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
        conn.commit()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()
    return user

def set_maintenance(status: str):
    cursor.execute("UPDATE settings SET value = ? WHERE name = 'maintenance'", (status,))
    conn.commit()

def get_maintenance():
    cursor.execute("SELECT value FROM settings WHERE name = 'maintenance'")
    return cursor.fetchone()[0]

# ================== КЛАВИАТУРЫ ==================
def main_menu(is_admin=False):
    kb = InlineKeyboardBuilder()
    kb.row(
        types.InlineKeyboardButton(text="Клик!", callback_data="click"),
        types.InlineKeyboardButton(text="Профиль", callback_data="profile")
    )
    kb.row(
        types.InlineKeyboardButton(text="Рейтинг", callback_data="rating"),
        types.InlineKeyboardButton(text="Магазин", callback_data="shop")
    )
    if is_admin:
        kb.add(types.InlineKeyboardButton(text="Админ меню", callback_data="admin"))
    return kb.as_markup()

def shop_menu():
    kb = InlineKeyboardBuilder()
    kb.add(types.InlineKeyboardButton(text="Премиум — 5000 очков (+50 кликов)", callback_data="buy_premium"))
    kb.add(types.InlineKeyboardButton(text="Ультра Премиум — 50000 очков", callback_data="buy_ultra"))
    kb.add(types.InlineKeyboardButton(text="Назад", callback_data="back"))
    return kb.as_markup()

def admin_menu():
    kb = InlineKeyboardBuilder()
    kb.add(types.InlineKeyboardButton(text="Добавить очки/клики пользователю", callback_data="admin_add_points"))
    kb.add(types.InlineKeyboardButton(text="Посмотреть всех пользователей", callback_data="admin_list"))
    kb.add(types.InlineKeyboardButton(text="Удалить пользователя", callback_data="admin_delete"))
    kb.add(types.InlineKeyboardButton(text=f"Тех.перерыв: {get_maintenance().upper()}", callback_data="toggle_maintenance"))
    kb.add(types.InlineKeyboardButton(text="Назад", callback_data="back"))
    return kb.as_markup()

# ================== ХЕНДЛЕРЫ ==================
@dp.message()
async def start(message: types.Message):
    is_admin = message.from_user.id in ADMIN_IDS
    get_user(message.from_user.id, message.from_user.username)
    await message.answer(
        f"Привет, {message.from_user.first_name}! Добро пожаловать в Clicker Bot!",
        reply_markup=main_menu(is_admin)
    )

@dp.callback_query()
async def callback_handler(callback: types.CallbackQuery):
    user = get_user(callback.from_user.id, callback.from_user.username)
    is_admin = callback.from_user.id in ADMIN_IDS
    data = callback.data

    if get_maintenance() == "on" and data not in ["admin", "toggle_maintenance", "back", "admin_list", "admin_add_points", "admin_delete"]:
        await callback.answer("Сейчас технический перерыв! Действия недоступны.", show_alert=True)
        return

    # ---------------- Клик ----------------
    if data == "click":
        cursor.execute("SELECT premium FROM users WHERE user_id = ?", (user[0],))
        status = cursor.fetchone()[0]

        if status == "none" or status == "premium":
            total = 1
        elif status == "ultra":
            total = 250

        cursor.execute("UPDATE users SET points = points + ?, clicks = clicks + 1 WHERE user_id = ?", (total, user[0]))
        conn.commit()
        await callback.answer(f"Вы получили {total} очков!")

    # ---------------- Профиль ----------------
    elif data == "profile":
        await callback.message.answer(
            f"Профиль {callback.from_user.first_name}\n"
            f"ID: {user[0]}\n"
            f"Очки: {user[2]}\n"
            f"Статус: {user[3]}\n"
            f"Клики: {user[4]}"
        )

    # ---------------- Рейтинг ----------------
    elif data == "rating":
        cursor.execute("SELECT username, points FROM users ORDER BY points DESC LIMIT 10")
        top = cursor.fetchall()
        text = "🏆 Топ игроков:\n"
        for i, u in enumerate(top, 1):
            text += f"{i}. {u[0]} — {u[1]} очков\n"
        await callback.message.answer(text)

    # ---------------- Магазин ----------------
    elif data == "shop":
        await callback.message.answer("Магазин:", reply_markup=shop_menu())

    elif data == "buy_premium":
        if user[2] >= 5000:
            cursor.execute("UPDATE users SET points = points - 5000, premium = 'premium', clicks = clicks + 50 WHERE user_id = ?", (user[0],))
            conn.commit()
            await callback.answer("Вы купили Премиум! +50 кликов")
        else:
            await callback.answer("Недостаточно очков!", show_alert=True)

    elif data == "buy_ultra":
        if user[2] >= 50000:
            cursor.execute("UPDATE users SET points = points - 50000, premium = 'ultra' WHERE user_id = ?", (user[0],))
            conn.commit()
            await callback.answer("Вы купили Ультра Премиум!")
        else:
            await callback.answer("Недостаточно очков!", show_alert=True)

    # ---------------- Админ ----------------
    elif data == "admin" and is_admin:
        await callback.message.answer("Админ меню:", reply_markup=admin_menu())

    elif data == "toggle_maintenance" and is_admin:
        current = get_maintenance()
        new_status = "off" if current == "on" else "on"
        set_maintenance(new_status)
        await callback.message.answer(f"Технический перерыв теперь: {new_status.upper()}", reply_markup=admin_menu())

    elif data == "admin_list" and is_admin:
        cursor.execute("SELECT user_id, username, points, premium, clicks FROM users")
        users = cursor.fetchall()
        text = "Все пользователи:\n"
        for u in users:
            text += f"{u[1]} (ID:{u[0]}) — {u[2]} очков, {u[3]}, {u[4]} кликов\n"
        await callback.message.answer(text)

    elif data == "admin_add_points" and is_admin:
        await callback.message.answer("Введите ID пользователя, очки и клики через пробел, например:\n123456789 500 10")
        dp.register_message_handler(admin_add_points)

    elif data == "admin_delete" and is_admin:
        await callback.message.answer("Введите ID пользователя для удаления:")
        dp.register_message_handler(admin_delete_user)

    elif data == "back":
        await callback.message.answer("Главное меню:", reply_markup=main_menu(is_admin))

# ------------------- ФУНКЦИИ АДМИНА -------------------
async def admin_add_points(message: types.Message):
    try:
        parts = message.text.split()
        user_id = int(parts[0])
        points = int(parts[1]) if len(parts) > 1 else 0
        clicks = int(parts[2]) if len(parts) > 2 else 0
        cursor.execute("UPDATE users SET points = points + ?, clicks = clicks + ? WHERE user_id = ?", (points, clicks, user_id))
        conn.commit()
        await message.answer(f"Пользователю {user_id} добавлено: {points} очков, {clicks} кликов")
    except:
        await message.answer("Ошибка ввода. Формат: ID очки клики")
    dp.unregister_message_handler(admin_add_points)

async def admin_delete_user(message: types.Message):
    try:
        user_id = int(message.text)
        cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        conn.commit()
        await message.answer(f"Пользователь {user_id} удалён.")
    except:
        await message.answer("Ошибка ввода. Введите корректный ID")
    dp.unregister_message_handler(admin_delete_user)

# ================== ЗАПУСК ==================
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
