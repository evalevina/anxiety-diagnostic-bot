from yookassa import Configuration, Payment
import uuid
import time

from database import save_payment, get_saw_offer_at, get_recent_payment_url
from config import YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY, BOT_USERNAME

Configuration.account_id = YOOKASSA_SHOP_ID
Configuration.secret_key = YOOKASSA_SECRET_KEY


def create_payment_amount(user_id, amount, description, payment_type="product"):

    # Возвращаем существующий URL если платёж создан менее 30 минут назад
    existing_url = get_recent_payment_url(user_id, minutes=30)
    if existing_url:
        return existing_url

    return_url = f"https://t.me/{BOT_USERNAME}" if BOT_USERNAME else "https://t.me"

    payment = Payment.create(
        {
            "amount": {
                "value": f"{amount}.00",
                "currency": "RUB"
            },
            "capture": True,
            "confirmation": {
                "type": "redirect",
                "return_url": return_url
            },
            "description": f"{description} | user {user_id}"
        },
        uuid.uuid4()
    )

    url = payment.confirmation.confirmation_url
    save_payment(user_id, payment.id, payment_type, payment_url=url)

    return url


def check_payment_status(payment_id):

    payment = Payment.find_one(payment_id)
    return payment.status


def get_offer_price(user_id):
    """Возвращает 1490 если < 72ч с момента просмотра оффера, иначе 3490."""
    saw_at = get_saw_offer_at(user_id)
    if saw_at and (time.time() - saw_at) > 72 * 3600:
        return 3490
    return 1490


def create_payment_returning(user_id):
    """Платёж для вернувшегося пользователя — цена зависит от истечения 72ч."""
    price = get_offer_price(user_id)
    url = create_payment_amount(user_id, price, "Полный разбор тревоги", "product")
    return url, price
