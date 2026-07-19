import ipaddress
import json
import logging

from aiohttp import web

from database import set_bought, save_message, add_funnel_task, get_payment_type
from config import ADMIN_ID, WEBHOOK_SECRET
from materials import send_materials

logger = logging.getLogger(__name__)

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


async def start_webhook_server(bot, port=8080):

    app = web.Application()
    app["bot"] = bot
    app.router.add_post("/webhook", handle_yookassa)

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    logger.info(f"Webhook server started on port {port}")
