# Telegram-бот заказов аватарок (дизайнер и админ один человек)
# Стек: Python 3.10+, aiogram 3.x, SQLite

import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
import sqlite3

# ---------------- НАСТРОЙКИ ----------------
TOKEN = "8376239597:AAHYeacPDfZDso4h3RD07vDYNTj9w9dg3wY"
DESIGNER_ID = 7388659987  # дизайнер и админ
SBER_NUMBER = "+79936473112"

bot = Bot(TOKEN)
dp = Dispatcher()
logging.basicConfig(level=logging.INFO)

# ---------------- БАЗА ----------------
conn = sqlite3.connect("orders.db")
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    character TEXT,
    nickname TEXT,
    colors TEXT,
    details TEXT,
    status TEXT,
    paid INTEGER DEFAULT 0
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS designer_status (
    designer_id INTEGER PRIMARY KEY,
    online INTEGER DEFAULT 1
)
""")
conn.commit()

# ---------------- СОСТОЯНИЯ ----------------
class OrderState(StatesGroup):
    character = State()
    nickname = State()
    colors = State()
    details = State()
    waiting_payment = State()

# ---------------- /start ----------------
@dp.message(CommandStart())
async def start(msg: Message):
    kb = InlineKeyboardBuilder()
    if msg.from_user.id == DESIGNER_ID:
        kb.button(text="🟢 Онлайн/Офлайн", callback_data="toggle_status")
        kb.button(text="📦 Посмотреть заказы", callback_data="view_orders")
        await msg.answer("Привет, дизайнер! Вот твои команды:", reply_markup=kb.as_markup())
    else:
        kb.button(text="🎨 Заказать аватарку", callback_data="check_designer")
        await msg.answer("Привет! Закажи аватарку 👇", reply_markup=kb.as_markup())

# ---------------- Проверка дизайнера ----------------
@dp.callback_query(F.data == "check_designer")
async def check_designer(cb: CallbackQuery):
    cursor.execute("SELECT online FROM designer_status WHERE designer_id=?", (DESIGNER_ID,))
    row = cursor.fetchone()
    designer_online = row[0] == 1 if row else True

    if designer_online:
        await cb.message.answer("Дизайнер доступен ✅\nДавайте заполним анкету для заказа")
        await OrderState.character.set()
    else:
        await cb.message.answer("Дизайнер сейчас недоступен ❌")

# ---------------- Анкета ----------------
@dp.message(OrderState.character)
async def character(msg: Message, state: FSMContext):
    await state.update_data(character=msg.text)
    await OrderState.nickname.set()
    await msg.answer("Введите ник персонажа:")

@dp.message(OrderState.nickname)
async def nickname(msg: Message, state: FSMContext):
    await state.update_data(nickname=msg.text)
    await OrderState.colors.set()
    await msg.answer("Введите цвета:")

@dp.message(OrderState.colors)
async def colors(msg: Message, state: FSMContext):
    await state.update_data(colors=msg.text)
    await OrderState.details.set()
    await msg.answer("Дополнительные детали? (можно написать 'нет')")

@dp.message(OrderState.details)
async def details(msg: Message, state: FSMContext):
    data = await state.get_data()
    cursor.execute(
        "INSERT INTO orders (user_id, character, nickname, colors, details, status, paid) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (msg.from_user.id, data['character'], data['nickname'], data['colors'], msg.text, "new", 0)
    )
    conn.commit()
    order_id = cursor.lastrowid

    # ---------------- Уведомление дизайнеру ----------------
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Принять заказ", callback_data=f"accept_{order_id}")
    kb.button(text="❌ Отказать", callback_data=f"reject_{order_id}")

    await bot.send_message(
        DESIGNER_ID,
        f"🆕 Новый заказ #{order_id}\n\n"
        f"Персонаж: {data['character']}\n"
        f"Ник: {data['nickname']}\n"
        f"Цвета: {data['colors']}\n"
        f"Детали: {msg.text}",
        reply_markup=kb.as_markup()
    )

    await msg.answer("Ваш заказ отправлен дизайнеру на проверку ✅")
    await state.clear()

# ---------------- Дизайнер принимает/отказывает ----------------
@dp.callback_query(F.data.startswith("accept_"))
async def accept_order(cb: CallbackQuery):
    order_id = cb.data.split("_")[1]
    cursor.execute("UPDATE orders SET status='accepted' WHERE id=?", (order_id,))
    conn.commit()
    await cb.message.edit_text(f"Заказ #{order_id} принят ✅")
    user_id = cursor.execute("SELECT user_id FROM orders WHERE id=?", (order_id,)).fetchone()[0]
    await bot.send_message(user_id, f"Ваш заказ #{order_id} принят! 🎨\nОплатите на Сбер: {SBER_NUMBER} и отправьте скрин перевода")
    # переводим пользователя в состояние оплаты
    await OrderState.waiting_payment.set()

@dp.callback_query(F.data.startswith("reject_"))
async def reject_order(cb: CallbackQuery):
    order_id = cb.data.split("_")[1]
    cursor.execute("UPDATE orders SET status='rejected' WHERE id=?", (order_id,))
    conn.commit()
    await cb.message.edit_text(f"Заказ #{order_id} отклонён ❌")
    user_id = cursor.execute("SELECT user_id FROM orders WHERE id=?", (order_id,)).fetchone()[0]
    await bot.send_message(user_id, f"Ваш заказ #{order_id} отклонён дизайнером. Попробуйте оформить новый заказ.")

# ---------------- Подтверждение оплаты ----------------
@dp.message(OrderState.waiting_payment)
async def confirm_payment(msg: Message):
    if 'оплатил' in msg.text.lower():
        cursor.execute("UPDATE orders SET paid=1 WHERE user_id=?", (msg.from_user.id,))
        conn.commit()
        await msg.answer("Оплата подтверждена ✅\nДизайнер приступает к работе")
        # уведомление дизайнеру, что можно выполнять
        await bot.send_message(DESIGNER_ID, f"Пользователь {msg.from_user.full_name} оплатил заказ! Можно приступать.")
    else:
        await msg.answer("Пожалуйста, отправьте сообщение с текстом 'Оплатил' после перевода.")

# ---------------- Дизайнер отправляет готовую аватарку ----------------
@dp.message(F.photo | F.document, F.from_user.id == DESIGNER_ID)
async def send_result(msg: Message):
    order = cursor.execute("SELECT user_id FROM orders WHERE status='accepted' ORDER BY id DESC LIMIT 1").fetchone()
    if order:
        user_id = order[0]
        kb = InlineKeyboardBuilder()
        kb.button(text="⭐ Оставить отзыв", callback_data="review")
        await bot.send_message(user_id, "Ваша аватарка готова! 🎉", reply_markup=kb.as_markup())
        await msg.copy_to(user_id)
        cursor.execute("UPDATE orders SET status='done' WHERE user_id=?", (user_id,))
        conn.commit()

# ---------------- Оставить отзыв ----------------
@dp.callback_query(F.data == "review")
async def review(cb: CallbackQuery):
    await cb.message.answer("Спасибо за заказ! Напишите свой отзыв текстом ⭐")

# ---------------- Статус дизайнера ----------------
@dp.callback_query(F.data == "toggle_status")
async def toggle_status(cb: CallbackQuery):
    cursor.execute("SELECT online FROM designer_status WHERE designer_id=?", (DESIGNER_ID,))
    row = cursor.fetchone()
    current = row[0] == 1 if row else True
    new_status = 0 if current else 1
    cursor.execute("INSERT OR REPLACE INTO designer_status (designer_id, online) VALUES (?, ?)", (DESIGNER_ID, new_status))
    conn.commit()
    status_text = "Онлайн ✅" if new_status else "Офлайн ❌"
    await cb.message.edit_text(f"Статус дизайнера изменён: {status_text}")

# ---------------- RUN ----------------
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
