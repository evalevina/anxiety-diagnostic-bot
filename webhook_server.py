import hmac
import hashlib
import json
import logging

from aiohttp import web

from database import set_bought, save_message, add_funnel_task, get_payment_type
from config import ADMIN_ID, YOOKASSA_SECRET_KEY, WEBHOOK_SECRET
from materials import send_materials

logger = logging.getLogger(__name__)


def verify_yookassa_signature(body: bytes, signature: str) -> bool:
    expected = hmac.new(
        YOOKASSA_SECRET_KEY.encode(),
        body,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


async def handle_yookassa(request):

    try:

        # Проверяем секретный токен из URL (?secret=...)
        if WEBHOOK_SECRET:
            token = request.rel_url.query.get("secret", "")
            if token != WEBHOOK_SECRET:
                logger.warning("Webhook: неверный секретный токен — запрос отклонён")
                return web.Response(status=403)

        body = await request.read()
        signature = request.headers.get("Signature", "")

        if signature and not verify_yookassa_signature(body, signature):
            logger.warning("Webhook: неверная подпись — запрос отклонён")
            return web.Response(status=403)

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
