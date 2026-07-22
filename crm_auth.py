import hashlib
import hmac
import time

from config import CRM_PASSWORD, CRM_SESSION_SECRET

SESSION_TTL = 2592000  # 30 дней
COOKIE_NAME = "crm_session"

# Троттлинг брутфорса пароля — в памяти процесса (сбрасывается при рестарте
# бота, это не проблема: рестарты редкие, а после него счётчик просто с нуля).
_MAX_FAILS = 5
_FAIL_WINDOW = 900  # 15 минут
_fail_log = {}  # ip -> [timestamp, ...] неудачных попыток за окно


def is_ip_blocked(ip: str) -> bool:
    now = time.time()
    attempts = [t for t in _fail_log.get(ip, []) if now - t < _FAIL_WINDOW]
    _fail_log[ip] = attempts
    return len(attempts) >= _MAX_FAILS


def record_failed_attempt(ip: str):
    _fail_log.setdefault(ip, []).append(time.time())


def check_password(password: str) -> bool:
    if not CRM_PASSWORD or not password:
        return False
    return hmac.compare_digest(password, CRM_PASSWORD)


def make_session_token() -> str:
    expiry = int(time.time()) + SESSION_TTL
    signature = hmac.new(
        CRM_SESSION_SECRET.encode(), str(expiry).encode(), hashlib.sha256
    ).hexdigest()
    return f"{expiry}.{signature}"


def verify_session_token(token: str | None) -> bool:
    if not token or "." not in token:
        return False

    expiry_str, signature = token.split(".", 1)

    try:
        expiry = int(expiry_str)
    except ValueError:
        return False

    if time.time() > expiry:
        return False

    expected = hmac.new(
        CRM_SESSION_SECRET.encode(), expiry_str.encode(), hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected, signature)
