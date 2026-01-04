import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils import executor

# ----------------- НАСТРОЙКИ -----------------
TOKEN = "8376239597:AAHYeacPDfZDso4h3RD07vDYNTj9w9dg3wY"  # твой токен
ADMIN_IDS = [7388659987]  # твой ID

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

# ================== БАЗА ДАННЫХ ==================
conn = sqlite3.connect("clicker.db")
cursor = conn.cursor()

# Таблица пользователей
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    points INTEGER DEFAULT 0,
    premium TEXT DEFAULT 'none',
    clicks INTEGER DEFAULT 0
)
''')

# Таблица настроек (технический перерыв)
cursor.execute('''
CREATE TABLE IF NOT EXISTS settings (
    name TEXT PRIMARY KEY,
    value TEXT
)
''')
conn.commit()

# Инициализация технического перерыва
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
    return cursor.fetchone()[0]  # 'on' или 'off'

# ================== КЛАВИАТУРЫ ==================
def main_menu(is_admin=False):
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("Клик!", callback_data="click"),
        InlineKeyboardButton("Профиль", callback_data="profile"),
        InlineKeyboardButton("Рейтинг", callback_data="rating"),
        InlineKeyboardButton("Магазин", callback_data="shop")
    )
    if is_admin:
        kb.add(InlineKeyboardButton("Админ меню", callback_data="admin"))
    return kb

def shop_menu():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("Премиум — 100 очков", callback_data="buy_premium"),
        InlineKeyboardButton("Ультра Премиум — 500 очков", callback_data="buy_ultra"),
        InlineKeyboardButton("Назад", callback_data="back")
    )
    return kb

def admin_menu():
    kb = InlineKeyboardMarkup(row_width=1)
    maintenance_status = get_maintenance()
    kb.add(
        InlineKeyboardButton("Добавить очки пользователю", callback_data="admin_add_points"),
        InlineKeyboardButton("Посмотреть всех пользователей", callback_data="admin_list"),
        InlineKeyboardButton("Удалить пользователя", callback_data="admin_delete"),
        InlineKeyboardButton(f"Тех.перерыв: {maintenance_status.upper()}", callback_data="toggle_maintenance"),
        InlineKeyboardButton("Назад", callback_data="back")
    )
    return kb

# ================== ХЕНДЛЕРЫ ==================
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    is_admin = message.from_user.id in ADMIN_IDS
    user = get_user(message.from_user.id, message.from_user.username)
    await message.answer(
        f"Привет, {message.from_user.first_name}! Добро пожаловать в Clicker Bot!",
        reply_markup=main_menu(is_admin)
    )

# ------------------- CALLBACK -------------------
@dp.callback_query_handler(lambda c: True)
async def callback_handler(callback: types.CallbackQuery):
    user = get_user(callback.from_user.id, callback.from_user.username)
    is_admin = callback.from_user.id in ADMIN_IDS
    data = callback.data

    # -------- Проверка технического перерыва --------
    if get_maintenance() == "on" and data not in ["admin", "toggle_maintenance", "back", "admin_list", "admin_add_points", "admin_delete"]:
        await callback.answer("Сейчас технический перерыв! Действия недоступны.", show_alert=True)
        return

    # -------- Клик --------
    if data == "click":
        # увеличиваем счётчик кликов
        cursor.execute("UPDATE users SET clicks = clicks + 1 WHERE user_id = ?", (user[0],))
        conn.commit()
        cursor.execute("SELECT clicks, premium, points FROM users WHERE user_id = ?", (user[0],))
        clicks, status, points = cursor.fetchone()

        # базовые очки и бонусы
        base_points = 1
        bonus = 0
        if status == "none":
            base_points = 1
        elif status == "premium":
            base_points = 2
            if clicks % 10 == 0:  # каждые 10 кликов бонус
                bonus = 1
        elif status == "ultra":
            base_points = 5
            if clicks % 5 == 0:  # каждый 5-й клик удвоение
                bonus = base_points

        total = base_points + bonus
        cursor.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (total, user[0]))
        conn.commit()
        await callback.answer(f"Вы получили {total} очков! (Бонус: {bonus})")

    # -------- Профиль --------
    elif data == "profile":
        await callback.message.answer(
            f"Профиль {callback.from_user.first_name}\n"
            f"Очки: {user[2]}\n"
            f"Статус: {user[3]}\n"
            f"Клики: {user[4]}"
        )

    # -------- Рейтинг --------
    elif data == "rating":
        cursor.execute("SELECT username, points FROM users ORDER BY points DESC LIMIT 10")
        top = cursor.fetchall()
        text = "🏆 Топ игроков:\n"
        for i, u in enumerate(top, 1):
            text += f"{i}. {u[0]} — {u[1]} очков\n"
        await callback.message.answer(text)

    # -------- Магазин --------
    elif data == "shop":
        await callback.message.answer("Магазин:", reply_markup=shop_menu())

    elif data == "buy_premium":
        if user[2] >= 100:
            cursor.execute("UPDATE users SET points = points - 100, premium = 'premium' WHERE user_id = ?", (user[0],))
            conn.commit()
            await callback.answer("Вы купили Премиум!")
        else:
            await callback.answer("Недостаточно очков!", show_alert=True)

    elif data == "buy_ultra":
        if user[2] >= 500:
            cursor.execute("UPDATE users SET points = points - 500, premium = 'ultra' WHERE user_id = ?", (user[0],))
            conn.commit()
            await callback.answer("Вы купили Ультра Премиум!")
        else:
            await callback.answer("Недостаточно очков!", show_alert=True)

    # -------- Админ меню --------
    elif data == "admin" and is_admin:
        await callback.message.answer("Админ меню:", reply_markup=admin_menu())

    elif data == "toggle_maintenance" and is_admin:
        current = get_maintenance()
        new_status = "off" if current == "on" else "on"
        set_maintenance(new_status)
        await callback.message.answer(f"Технический перерыв теперь: {new_status.upper()}", reply_markup=admin_menu())

    elif data == "admin_list" and is_admin:
        cursor.execute("SELECT user_id, username, points, premium FROM users")
        users = cursor.fetchall()
        text = "Все пользователи:\n"
        for u in users:
            text += f"{u[1]} ({u[0]}) — {u[2]} очков, {u[3]}\n"
        await callback.message.answer(text)

    elif data == "admin_add_points" and is_admin:
        await callback.message.answer("Введите ID пользователя и количество очков через пробел, например:\n123456789 50")
        dp.register_message_handler(admin_add_points)

    elif data == "admin_delete" and is_admin:
        await callback.message.answer("Введите ID пользователя для удаления:")
        dp.register_message_handler(admin_delete_user)

    elif data == "back":
        await callback.message.answer("Главное меню:", reply_markup=main_menu(is_admin))

# ------------------- ФУНКЦИИ АДМИНА -------------------
async def admin_add_points(message: types.Message):
    try:
        user_id, points = message.text.split()
        points = int(points)
        cursor.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (points, int(user_id)))
        conn.commit()
        await message.answer(f"Добавлено {points} очков пользователю {user_id}")
    except:
        await message.answer("Ошибка ввода. Формат: ID очки")
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
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
