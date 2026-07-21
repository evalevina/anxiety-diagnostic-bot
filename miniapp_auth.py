import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

from config import BOT_TOKEN

# Максимальный возраст initData, после которого запрос считается устаревшим.
# Официальной рекомендации Telegram нет, 24ч — стандартная практика.
MAX_INIT_DATA_AGE = 86400


def verify_init_data(init_data: str) -> dict | None:
    """Проверяет подлинность Telegram WebApp initData по алгоритму из
    https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
    Возвращает словарь пользователя ({"id": ..., "first_name": ..., ...}) при успехе, иначе None.
    """

    if not init_data:
        return None

    try:
        pairs = dict(parse_qsl(init_data, strict_parsing=True))
    except ValueError:
        return None

    received_hash = pairs.pop("hash", None)
    if not received_hash:
        return None

    data_check_string = "\n".join(
        f"{key}={value}" for key, value in sorted(pairs.items())
    )

    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        return None

    auth_date = pairs.get("auth_date")
    if not auth_date or time.time() - int(auth_date) > MAX_INIT_DATA_AGE:
        return None

    user_raw = pairs.get("user")
    if not user_raw:
        return None

    try:
        return json.loads(user_raw)
    except json.JSONDecodeError:
        return None
