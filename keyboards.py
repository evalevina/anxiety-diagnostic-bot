from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

MAIN_MENU = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📅 Записаться"), KeyboardButton(text="📖 О проекте")],
        [KeyboardButton(text="💬 Задать вопрос"), KeyboardButton(text="🤖 AI - компаньон")],
        [KeyboardButton(text="📔 Дневник"), KeyboardButton(text="🎁 Пригласить подругу")],
    ],
    resize_keyboard=True
)
