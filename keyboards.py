from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo

from config import MINIAPP_URL

# Пока MINIAPP_URL не настроен (домен ещё не выбран), кнопка остаётся
# обычной и ведёт в старый чатовый календарь (handlers/booking.py) —
# Telegram отклоняет web_app-кнопки без https-адреса.
if MINIAPP_URL:
    _booking_button = KeyboardButton(
        text="📅 Записаться",
        web_app=WebAppInfo(url=f"{MINIAPP_URL}/index.html?screen=booking")
    )
else:
    _booking_button = KeyboardButton(text="📅 Записаться")

_menu_rows = [
    [_booking_button, KeyboardButton(text="📖 О проекте")],
    [KeyboardButton(text="💬 Задать вопрос"), KeyboardButton(text="🤖 AI - компаньон")],
    [KeyboardButton(text="📔 Дневник"), KeyboardButton(text="🎁 Пригласить подругу")],
]

# Личный кабинет — это надстройка Mini App без чатового аналога, поэтому
# кнопка появляется в меню только когда домен настроен.
if MINIAPP_URL:
    _menu_rows.append([
        KeyboardButton(
            text="🗂 Личный кабинет",
            web_app=WebAppInfo(url=f"{MINIAPP_URL}/index.html?screen=cabinet")
        )
    ])

MAIN_MENU = ReplyKeyboardMarkup(keyboard=_menu_rows, resize_keyboard=True)
