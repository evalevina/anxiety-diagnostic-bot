from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

from config import MINIAPP_URL

# Кнопки нижнего меню (reply-клавиатура) — обычный текст, а не web_app:
# у части клиентов (подтверждено на Telegram Desktop и iOS, версия бриджа
# 9.6) web_app-кнопка в reply-клавиатуре открывает Mini App без подписанного
# initData — сервер не может проверить, кто это. Инлайн-кнопка под
# сообщением его получает исправно, поэтому Mini App открывается через неё
# (см. handlers/booking.py::cmd_booking и handlers/start.py::cmd_cabinet).
_menu_rows = [
    [KeyboardButton(text="📅 Записаться"), KeyboardButton(text="📖 О проекте")],
    [KeyboardButton(text="💬 Задать вопрос"), KeyboardButton(text="🤖 AI - компаньон")],
    [KeyboardButton(text="📔 Дневник"), KeyboardButton(text="🎁 Пригласить подругу")],
]

# Личный кабинет — это надстройка Mini App без чатового аналога, поэтому
# кнопка появляется в меню только когда домен настроен.
if MINIAPP_URL:
    _menu_rows.append([KeyboardButton(text="🗂 Личный кабинет")])

MAIN_MENU = ReplyKeyboardMarkup(keyboard=_menu_rows, resize_keyboard=True)
