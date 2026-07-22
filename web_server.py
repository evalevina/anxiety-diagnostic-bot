import asyncio
import ipaddress
import json
import logging
import os
from datetime import date, timedelta

from aiohttp import web
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from database import (
    set_bought, save_message, add_funnel_task, get_payment_type,
    get_taken_times, get_blocked_times, is_date_fully_blocked,
    save_booking, get_user_type, get_latest_payment_id, get_payment_owner,
    get_quiz_result_latest, get_quiz_result_history, get_user_bookings,
    get_diary_history,
)
from config import ADMIN_ID, WEBHOOK_SECRET, SESSION_PRICE
from materials import send_materials
from miniapp_auth import verify_init_data
from handlers.booking import SLOTS, TYPE_NAMES, MONTH_GEN, DAY_NAMES
from yookassa_payment import create_payment_amount, check_payment_status, get_offer_price
from results_data import RESULTS

logger = logging.getLogger(__name__)

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_MINIAPP_DIR = os.path.join(_BASE_DIR, "miniapp")
_IMAGES_DIR = os.path.join(_BASE_DIR, "images")

# ЮKassa не подписывает уведомления HMAC-заголовком (в отличие от Stripe и
# похожих провайдеров) — их официальный способ проверки подлинности это
# сверка IP отправителя со списком их серверов уведомлений:
# https://yookassa.ru/docs/support/merchant/payments/http-notifications
_YOOKASSA_NETWORKS = [
    ipaddress.ip_network(net) for net in (
        "185.71.76.0/27", "185.71.77.0/27",
        "77.75.153.0/25", "77.75.154.128/25",
        "2a02:5180:0:1509::/64", "2a02:5180:0:2655::/64",
        "2a02:5180:0:1533::/64", "2a02:5180:0:2669::/64",
    )
]


def _is_yookassa_ip(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    return any(ip in net for net in _YOOKASSA_NETWORKS)


async def handle_yookassa(request):

    try:

        # Проверяем секретный токен из URL (?secret=...)
        if WEBHOOK_SECRET:
            token = request.rel_url.query.get("secret", "")
            if token != WEBHOOK_SECRET:
                logger.warning("Webhook: неверный секретный токен — запрос отклонён")
                return web.Response(status=403)

        # nginx перед этим сервером прокидывает реальный IP клиента в
        # X-Real-IP (см. /etc/nginx/sites-enabled) — сам aiohttp видит
        # только локальный адрес nginx, поэтому смотрим на заголовок.
        client_ip = request.headers.get("X-Real-IP", request.remote or "")
        if not _is_yookassa_ip(client_ip):
            logger.warning(f"Webhook: запрос не с IP ЮKassa ({client_ip}) — отклонён")
            return web.Response(status=403)

        body = await request.read()
        data = json.loads(body)

        event = data.get("event", "")
        obj = data.get("object", {})

        if event == "payment.succeeded" and obj.get("status") == "succeeded":

            description = obj.get("description", "")
            payment_id = obj.get("id", "unknown")

            user_id = None
            if "user " in description:
                try:
                    raw = description.split("user ")[-1].strip().split()[0]
                    user_id = int(raw)
                except (ValueError, IndexError):
                    logger.error(f"Webhook: не удалось извлечь user_id из описания '{description}'")

            if user_id is None:
                logger.error(f"Webhook: user_id не найден, payment_id={payment_id}")
                return web.Response(status=200)

            bot = request.app["bot"]

            payment_type = get_payment_type(payment_id)

            if payment_type == "session":

                await bot.send_message(
                    user_id,
                    "✅ Оплата сессии прошла успешно!\n\n"
                    "Я свяжусь с тобой в ближайшее время для подтверждения времени 🤍"
                )

                await bot.send_message(
                    ADMIN_ID,
                    f"📅 Новая запись на сессию!\n\n"
                    f"User ID: {user_id}\n"
                    f"Payment ID: {payment_id}\n"
                    f"Сумма: {obj.get('amount', {}).get('value', '?')} ₽"
                )

            else:

                set_bought(user_id)
                save_message(user_id, "bot", "✅ Оплата подтверждена автоматически")

                await send_materials(bot, user_id)

                add_funnel_task(user_id, 86400, "onboarding_day1")
                add_funnel_task(user_id, 259200, "review_3d")
                add_funnel_task(user_id, 604800, "upsell2_7d")

                await bot.send_message(
                    ADMIN_ID,
                    f"💳 Новая оплата разбора!\n\n"
                    f"User ID: {user_id}\n"
                    f"Payment ID: {payment_id}"
                )

    except Exception as e:
        logger.error(f"Webhook error: {e}", exc_info=True)

    return web.Response(status=200)


# ---------------- MINI APP: БРОНИРОВАНИЕ ----------------


def _free_slots(date_str: str):
    """Свободные слоты на дату или None, если дата вне допустимого диапазона
    записи (та же логика доступности, что и в handlers/booking.py::_time_kb)."""

    try:
        year, month, day = int(date_str[:4]), int(date_str[4:6]), int(date_str[6:])
        d = date(year, month, day)
    except (ValueError, IndexError):
        return None

    today = date.today()
    max_date = today + timedelta(days=60)
    if d <= today or d > max_date or d.weekday() == 6:  # воскресенье не работаем
        return None

    if is_date_fully_blocked(date_str):
        return []

    unavailable = set(get_taken_times(date_str)) | set(get_blocked_times(date_str))
    return [s for s in SLOTS if s not in unavailable]


async def handle_booking_slots(request):
    date_str = request.rel_url.query.get("date", "")
    init_data = request.rel_url.query.get("initData", "")

    if not verify_init_data(init_data):
        return web.json_response({"error": "unauthorized"}, status=401)

    slots = _free_slots(date_str)
    if slots is None:
        return web.json_response({"error": "invalid_date"}, status=400)

    return web.json_response({"free": slots})


async def handle_booking_book(request):
    try:
        data = await request.json()
    except json.JSONDecodeError:
        return web.json_response({"error": "bad_request"}, status=400)

    user = verify_init_data(data.get("initData", ""))
    if not user:
        return web.json_response({"error": "unauthorized"}, status=401)

    date_str = data.get("date", "")
    time_str = data.get("time", "")
    concern = (data.get("concern") or "").strip()

    if not concern:
        return web.json_response({"error": "concern_required"}, status=400)

    slots = _free_slots(date_str)
    if slots is None or time_str not in slots:
        return web.json_response({"error": "slot_unavailable"}, status=409)

    year, month, day = int(date_str[:4]), int(date_str[4:6]), int(date_str[6:])
    d = date(year, month, day)
    date_pretty = f"{day} {MONTH_GEN[month]}, {DAY_NAMES[d.weekday()]}"

    user_id = user["id"]
    first_name = user.get("first_name", "")
    username = f"@{user['username']}" if user.get("username") else "без username"

    anxiety_type = get_user_type(user_id)
    type_label = TYPE_NAMES.get(anxiety_type, "не определён") if anxiety_type else "не определён"

    save_booking(user_id, f"{date_pretty} в {time_str}", date_str, time_str)

    bot = request.app["bot"]

    admin_kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"bk_ok_{user_id}_{date_str}_{time_str}"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"bk_no_{user_id}_{date_str}_{time_str}"),
    ]])

    await bot.send_message(
        ADMIN_ID,
        f"📅 *Новая запись (Mini App)!*\n\n"
        f"👤 {first_name} {username}\n"
        f"ID: `{user_id}`\n"
        f"Тип тревоги: {type_label}\n"
        f"🕐 {date_pretty.capitalize()} в {time_str}\n\n"
        f"💬 Запрос: _{concern}_",
        parse_mode="Markdown",
        reply_markup=admin_kb
    )

    await bot.send_message(
        user_id,
        f"⏳ Запрос отправлен!\n\n"
        f"📅 {date_pretty.capitalize()} в {time_str}\n\n"
        f"Ева подтвердит запись в ближайшее время — и я тебе напишу 🤍"
    )

    return web.json_response({"ok": True})


# ---------------- MINI APP: ОПЛАТА ----------------

_PAYMENT_DESCRIPTIONS = {
    "session": "Сессия с психологом",
    "product": "Полный разбор тревоги",
}


async def handle_payment_create(request):
    try:
        data = await request.json()
    except json.JSONDecodeError:
        return web.json_response({"error": "bad_request"}, status=400)

    user = verify_init_data(data.get("initData", ""))
    if not user:
        return web.json_response({"error": "unauthorized"}, status=401)

    payment_type = data.get("payment_type", "")
    if payment_type not in _PAYMENT_DESCRIPTIONS:
        return web.json_response({"error": "bad_payment_type"}, status=400)

    user_id = user["id"]
    amount = SESSION_PRICE if payment_type == "session" else get_offer_price(user_id)
    description = _PAYMENT_DESCRIPTIONS[payment_type]

    try:
        loop = asyncio.get_running_loop()
        url = await loop.run_in_executor(
            None, create_payment_amount, user_id, amount, description, payment_type
        )
        payment_id = await loop.run_in_executor(None, get_latest_payment_id, user_id)
    except Exception as e:
        logger.error("Mini App payment creation failed: %s", e)
        return web.json_response({"error": "payment_failed"}, status=502)

    return web.json_response({"url": url, "payment_id": payment_id, "amount": amount})


async def handle_payment_status(request):
    init_data = request.rel_url.query.get("initData", "")
    payment_id = request.rel_url.query.get("payment_id", "")

    user = verify_init_data(init_data)
    if not user:
        return web.json_response({"error": "unauthorized"}, status=401)

    if not payment_id or get_payment_owner(payment_id) != user["id"]:
        return web.json_response({"error": "not_found"}, status=404)

    try:
        loop = asyncio.get_running_loop()
        status = await loop.run_in_executor(None, check_payment_status, payment_id)
    except Exception as e:
        logger.error("Mini App payment status check failed: %s", e)
        return web.json_response({"error": "status_failed"}, status=502)

    return web.json_response({"status": status})


# ---------------- MINI APP: РЕЗУЛЬТАТЫ КВИЗА ----------------


def _result_summary(anxiety_type, created_at):
    result_data = RESULTS.get(anxiety_type)
    if not result_data:
        return None
    return {
        "type": anxiety_type,
        "created_at": created_at,
        "name": result_data["name"],
        "image": f"/miniapp/images/{result_data['image']}",
    }


async def handle_results_latest(request):
    user = verify_init_data(request.rel_url.query.get("initData", ""))
    if not user:
        return web.json_response({"error": "unauthorized"}, status=401)

    latest = get_quiz_result_latest(user["id"])
    if not latest or latest[0] not in RESULTS:
        return web.json_response({"result": None})

    anxiety_type, created_at = latest
    result_data = RESULTS[anxiety_type]

    return web.json_response({"result": {
        "type": anxiety_type,
        "created_at": created_at,
        "name": result_data["name"],
        "text": result_data["text"],
        "exercise": result_data["exercise"],
        "image": f"/miniapp/images/{result_data['image']}",
    }})


async def handle_results_history(request):
    user = verify_init_data(request.rel_url.query.get("initData", ""))
    if not user:
        return web.json_response({"error": "unauthorized"}, status=401)

    history = get_quiz_result_history(user["id"])
    items = [s for s in (_result_summary(t, c) for t, c in history) if s]

    return web.json_response({"history": items})


# ---------------- MINI APP: ЛИЧНЫЙ КАБИНЕТ ----------------


def _pretty_date(date_str):
    try:
        year, month, day = int(date_str[:4]), int(date_str[4:6]), int(date_str[6:])
        d = date(year, month, day)
        return f"{day} {MONTH_GEN[month]}, {DAY_NAMES[d.weekday()]}"
    except (ValueError, TypeError, IndexError):
        return date_str


async def handle_cabinet(request):
    user = verify_init_data(request.rel_url.query.get("initData", ""))
    if not user:
        return web.json_response({"error": "unauthorized"}, status=401)

    user_id = user["id"]

    latest = get_quiz_result_latest(user_id)
    result = _result_summary(*latest) if latest else None

    bookings = [
        {"date": d, "date_label": _pretty_date(d), "time": t, "status": s, "created_at": c}
        for d, t, s, c in get_user_bookings(user_id)
    ]

    diary = [
        {"score": score, "note": note, "created_at": c}
        for score, note, c in get_diary_history(user_id, days=365)
    ]

    return web.json_response({"result": result, "bookings": bookings, "diary": diary})


async def start_web_server(bot, port=8080):

    app = web.Application()
    app["bot"] = bot
    app.router.add_post("/webhook", handle_yookassa)
    app.router.add_get("/api/booking/slots", handle_booking_slots)
    app.router.add_post("/api/booking/book", handle_booking_book)
    app.router.add_post("/api/payment/create", handle_payment_create)
    app.router.add_get("/api/payment/status", handle_payment_status)
    app.router.add_get("/api/results/latest", handle_results_latest)
    app.router.add_get("/api/results/history", handle_results_history)
    app.router.add_get("/api/cabinet", handle_cabinet)
    # /miniapp/images/ до /miniapp/ — картинки квиза отдаём из отдельной папки
    # bot/images/ (не дублируем в miniapp/), но в том же внешнем неймспейсе,
    # чтобы на сервере не пришлось заводить ещё один nginx location.
    app.router.add_static("/miniapp/images/", path=_IMAGES_DIR, show_index=False)
    app.router.add_static("/miniapp/", path=_MINIAPP_DIR, show_index=False)

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    logger.info(f"Web server started on port {port}")
