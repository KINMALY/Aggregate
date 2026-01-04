# Telegram-бот заказов аватарок с управлением статуса дизайнера и оплатой через Сбер
# Стек: Python 3.10+, aiogram 3.x, SQLite

import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, InputFile, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
import sqlite3

# --------- НАСТРОЙКИ БОТА ---------
TOKEN = "8376239597:AAHYeacPDfZDso4h3RD07vDYNTj9w9dg3wY"
DESIGNER_ID = 7388659987  # Telegram ID дизайнера и админа
SBER_NUMBER = "+79936473112"  # Номер Сбер для оплаты

bot = Bot(TOKEN)
dp = Dispatcher()
logging.basicConfig(level=logging.INFO)

# ---------- БАЗА ДАННЫХ ----------
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

# ---------- СОСТОЯНИЯ ----------
class OrderState(StatesGroup):
    character = State()
    nickname = State()
    colors = State()
    details = State()
    payment_confirmation = State()

# ---------- START ----------
@dp.message(CommandStart())
async def start(msg: Message):
    kb = InlineKeyboardBuilder()
    kb.button(text="🎨 Заказать аватарку", callback_data="check_designer")
    await msg.answer("Привет! Закажи аватарку 👇", reply_markup=kb.as_markup())

# ---------- ПРОВЕРКА СТАТУСА ДИЗАЙНЕРА ----------
@dp.callback_query(F.data == "check_designer")
async def check_designer(cb: CallbackQuery):
    cursor.execute("SELECT online FROM designer_status WHERE designer_id=?", (DESIGNER_ID,))
    row = cursor.fetchone()
    designer_online = row[0] == 1 if row else True

    if designer_online:
        kb = InlineKeyboardBuilder()
        kb.button(text=f"💳 Оплатить через Сбер {SBER_NUMBER}", callback_data="payment_sber")
        await cb.message.answer("Дизайнер доступен ✅\nОплати и оставь заявку!", reply_markup=kb.as_markup())
    else:
        await cb.message.answer("Дизайнер сейчас недоступен ❌")

# ---------- ОПЛАТА ЧЕРЕЗ СБЕР ----------
@dp.callback_query(F.data == "payment_sber")
async def payment_sber(cb: CallbackQuery, state: FSMContext):
    await cb.message.answer(f"После оплаты на номер {SBER_NUMBER} отправь сообщение 'Оплатил' и прикрепи скрин перевода")
    await state.set_state(OrderState.payment_confirmation)

@dp.message(OrderState.payment_confirmation)
async def confirm_payment(msg: Message, state: FSMContext):
    if 'оплатил' in msg.text.lower() and (msg.photo or msg.document):
        await msg.answer("Оплата подтверждена ✅ Ответь на вопросы для заказа")
        await state.set_state(OrderState.character)
    else:
        await msg.answer("Пожалуйста, отправь сообщение с текстом 'Оплатил' и приложи скрин перевода")

# ---------- АНКЕТА ----------
@dp.message(OrderState.character)
async def character(msg: Message, state: FSMContext):
    await state.update_data(character=msg.text)
    await state.set_state(OrderState.nickname)
    await msg.answer("Какой ник?")

@dp.message(OrderState.nickname)
async def nickname(msg: Message, state: FSMContext):
    await state.update_data(nickname=msg.text)
    await state.set_state(OrderState.colors)
    await msg.answer("Цвета?")

@dp.message(OrderState.colors)
async def colors(msg: Message, state: FSMContext):
    await state.update_data(colors=msg.text)
    await state.set_state(OrderState.details)
    await msg.answer("Дополнительные детали? (можно написать 'нет')")

@dp.message(OrderState.details)
async def details(msg: Message, state: FSMContext):
    data = await state.get_data()
    cursor.execute(
        "INSERT INTO orders (user_id, character, nickname, colors, details, status, paid) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (msg.from_user.id, data['character'], data['nickname'], data['colors'], msg.text, "new", 1)
    )
    conn.commit()
    order_id = cursor.lastrowid

    await msg.answer("Заказ принят! 🎉")

    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Готово", callback_data=f"done_{order_id}")

    await bot.send_message(
        DESIGNER_ID,
        f"🆕 Новый заказ #{order_id}\n\n"
        f"Персонаж: {data['character']}\n"
        f"Ник: {data['nickname']}\n"
        f"Цвета: {data['colors']}\n"
        f"Детали: {msg.text}",
        reply_markup=kb.as_markup()
    )

    await state.clear()

# ---------- СМЕНА СТАТУСА ДИЗАЙНЕРА ----------
@dp.message(F.from_user.id == DESIGNER_ID, F.text.lower().startswith("статус"))
async def change_status(msg: Message):
    if 'вкл' in msg.text.lower():
        cursor.execute("INSERT OR REPLACE INTO designer_status (designer_id, online) VALUES (?, ?)" , (DESIGNER_ID,1))
        conn.commit()
        await msg.answer("Статус дизайнера: Онлайн ✅")
    elif 'выкл' in msg.text.lower():
        cursor.execute("INSERT OR REPLACE INTO designer_status (designer_id, online) VALUES (?, ?)" , (DESIGNER_ID,0))
        conn.commit()
        await msg.answer("Статус дизайнера: Офлайн ❌")
    else:
        await msg.answer("Используй 'статус вкл' или 'статус выкл'")

# ---------- ДИЗАЙНЕР ----------
@dp.callback_query(F.data.startswith("done_"))
async def done(cb: CallbackQuery):
    order_id = cb.data.split("_")[1]
    cursor.execute("UPDATE orders SET status='done' WHERE id=?", (order_id,))
    conn.commit()
    await cb.message.answer("Отправь готовую аватарку файлом")

@dp.message(F.photo | F.document, F.from_user.id == DESIGNER_ID)
async def send_result(msg: Message):
    cursor.execute("SELECT user_id FROM orders WHERE status='done' ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    if row:
        user_id = row[0]
        kb = InlineKeyboardBuilder()
        kb.button(text="⭐ Оставить отзыв", callback_data="review")
        await bot.send_message(user_id, "Ваша аватарка готова! 🎉")
        await msg.copy_to(user_id, reply_markup=kb.as_markup())

# ---------- ОТЗЫВ ----------
@dp.callback_query(F.data == "review")
async def review(cb: CallbackQuery):
    await cb.message.answer("Спасибо за заказ! Напиши отзыв текстом ⭐")

# ---------- RUN ----------
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
