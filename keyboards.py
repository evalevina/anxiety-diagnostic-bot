from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo

from config import MINIAPP_URL

# Пока MINIAPP_URL не настроен (домен ещё не выбран), кнопка остаётся
# обычной и ведёт в старый чатовый календарь (handlers/booking.py) —
# Telegram отклоняет web_app-кнопки без https-адреса.
if MINIAPP_URL:
    _booking_button = KeyboardButton(
        text="📅 Записаться",
        web_app=WebAppInfo(url=f"{MINIAPP_URL}/?screen=booking")
    )
else:
    _booking_button = KeyboardButton(text="📅 Записаться")

MAIN_MENU = ReplyKeyboardMarkup(
    keyboard=[
        [_booking_button, KeyboardButton(text="📖 О проекте")],
        [KeyboardButton(text="💬 Задать вопрос"), KeyboardButton(text="🤖 AI - компаньон")],
        [KeyboardButton(text="📔 Дневник"), KeyboardButton(text="🎁 Пригласить подругу")],
    ],
    resize_keyboard=True
)
