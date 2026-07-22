import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
BOT_USERNAME = os.getenv("BOT_USERNAME", "")
PAYMENT_LINK = os.getenv("PAYMENT_URL", "")
SESSION_LINK = os.getenv("SESSION_URL", "")
MATERIALS_LINK = os.getenv("MATERIALS_URL", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_PROXY_URL = os.getenv("ANTHROPIC_PROXY_URL", "")

YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID", "")
YOOKASSA_SECRET_KEY = os.getenv("YOOKASSA_SECRET_KEY", "")

PDF_SCANNER = os.getenv("PDF_SCANNER", "")
PDF_CATASTROPHIST = os.getenv("PDF_CATASTROPHIST", "")
PDF_FREEZER = os.getenv("PDF_FREEZER", "")
PDF_CONTROLLER = os.getenv("PDF_CONTROLLER", "")

SESSION_PRICE = int(os.getenv("SESSION_PRICE", "5000"))
PRODUCT_PRICE = int(os.getenv("PRODUCT_PRICE", "1490"))
GROUP_PROGRAM_PRICE = int(os.getenv("GROUP_PROGRAM_PRICE", "3000"))
GROUP_PROGRAM_LINK = os.getenv("GROUP_PROGRAM_LINK", "")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")

# Базовый HTTPS-адрес, по которому отдаётся Mini App (например
# "https://miniapp.evalevina.dev/miniapp"). Пока пусто — кнопки открытия
# Mini App в чате отключены, бот работает как раньше.
MINIAPP_URL = os.getenv("MINIAPP_URL", "")

# Бампать при каждом деплое статики miniapp/ — Telegram WebView кэширует
# index.html по точному URL и не всегда уважает Cache-Control на уже
# сохранённой копии, так что смена файлов на сервере может быть не видна
# в уже открытом Mini App, пока не поменяется сам входной URL.
MINIAPP_VERSION = "6"


def miniapp_url(screen, **params):
    from urllib.parse import urlencode
    query = {"screen": screen, "v": MINIAPP_VERSION, **params}
    return f"{MINIAPP_URL}/index.html?{urlencode(query)}"
