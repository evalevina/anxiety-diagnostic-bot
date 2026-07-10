import sqlite3
import time

from config import PRODUCT_PRICE, SESSION_PRICE


def connect():
    return sqlite3.connect("users.db")


def init_db():

    conn = connect()
    cursor = conn.cursor()

    # пользователи

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        phone TEXT,
        anxiety_type TEXT,
        finished INTEGER DEFAULT 0,
        bought INTEGER DEFAULT 0,
        thinking INTEGER DEFAULT 0
    )
    """)

    for col in ["first_name TEXT", "last_name TEXT", "phone TEXT",
                "source TEXT", "saw_offer INTEGER DEFAULT 0",
                "saw_offer_at INTEGER", "started_quiz INTEGER DEFAULT 0",
                "health_consent INTEGER DEFAULT 0", "health_consent_at INTEGER"]:
        try:
            cursor.execute(f"ALTER TABLE users ADD COLUMN {col}")
        except Exception:
            pass

    # история диалогов

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        role TEXT,
        text TEXT,
        created_at INTEGER
    )
    """)

    # задачи воронки

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS funnel_tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        send_at INTEGER,
        message_type TEXT,
        sent INTEGER DEFAULT 0
    )
    """)

    # платежи

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        payment_id TEXT,
        payment_type TEXT DEFAULT 'product',
        created_at INTEGER
    )
    """)

    for col in ["payment_type TEXT DEFAULT 'product'", "payment_url TEXT"]:
        try:
            cursor.execute(f"ALTER TABLE payments ADD COLUMN {col}")
        except Exception:
            pass

    # дневник тревоги

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS diary (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        score INTEGER,
        note TEXT,
        created_at INTEGER
    )
    """)

    # разбор мыслей (CBT thought record)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS thought_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        diary_id INTEGER,
        automatic_thought TEXT,
        distortion TEXT,
        reframe TEXT,
        score_before INTEGER,
        score_after INTEGER,
        created_at INTEGER
    )
    """)

    # отзывы

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        text TEXT,
        created_at INTEGER
    )
    """)

    # записи на консультацию

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        preferred_time TEXT,
        created_at INTEGER
    )
    """)

    for col in ["date_str TEXT", "time_str TEXT", "status TEXT DEFAULT 'pending'"]:
        try:
            cursor.execute(f"ALTER TABLE bookings ADD COLUMN {col}")
        except Exception:
            pass

    # рефералы

    for col in ["referred_by INTEGER", "referral_count INTEGER DEFAULT 0",
                "unsubscribed INTEGER DEFAULT 0"]:
        try:
            cursor.execute(f"ALTER TABLE users ADD COLUMN {col}")
        except Exception:
            pass

    conn.commit()
    conn.close()


def save_user(user_id, username, first_name=None, last_name=None):

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT OR IGNORE INTO users
    (user_id, username, first_name, last_name)
    VALUES (?, ?, ?, ?)
    """, (user_id, username, first_name, last_name))

    conn.commit()
    conn.close()


def save_user_source(user_id, source):

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
    UPDATE users SET source=? WHERE user_id=? AND source IS NULL
    """, (source, user_id))

    conn.commit()
    conn.close()


def set_saw_offer(user_id):

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
    UPDATE users SET saw_offer=1, saw_offer_at=? WHERE user_id=?
    """, (int(time.time()), user_id))

    conn.commit()
    conn.close()


def get_saw_offer_at(user_id):

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("SELECT saw_offer_at FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()

    conn.close()

    return row[0] if row else None


def get_user_profile(user_id):
    """Returns (first_name, anxiety_type, bought, finished) or None."""

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT first_name, anxiety_type, bought, finished FROM users WHERE user_id=?
    """, (user_id,))
    row = cursor.fetchone()

    conn.close()

    return row if row else None


def get_user_ids_by_type(anxiety_type):

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("SELECT user_id FROM users WHERE anxiety_type=?", (anxiety_type,))
    rows = cursor.fetchall()

    conn.close()

    return [r[0] for r in rows]


def get_finished_count():

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM users WHERE finished=1")
    count = cursor.fetchone()[0]

    conn.close()

    return count


def get_referrer_id(user_id):

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("SELECT referred_by FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()

    conn.close()

    return row[0] if row and row[0] else None


def get_diary_streak(user_id):
    """Считает дни подряд с записями в дневнике."""
    from datetime import date, timedelta

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT DISTINCT date(created_at, 'unixepoch', 'localtime')
    FROM diary WHERE user_id=?
    ORDER BY 1 DESC
    """, (user_id,))

    dates = [row[0] for row in cursor.fetchall()]
    conn.close()

    if not dates:
        return 0

    today = date.today()
    streak = 0

    for i, d in enumerate(dates):
        if d == str(today - timedelta(days=i)):
            streak += 1
        else:
            break

    return streak


def get_last_diary_time(user_id):

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("SELECT MAX(created_at) FROM diary WHERE user_id=?", (user_id,))
    row = cursor.fetchone()

    conn.close()

    return row[0] if row else None


def has_diary_reminder_task(user_id):

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT COUNT(*) FROM funnel_tasks
    WHERE user_id=? AND message_type='diary_reminder' AND sent=0
    """, (user_id,))
    count = cursor.fetchone()[0]

    conn.close()

    return count > 0


def get_diary_stats():

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(DISTINCT user_id) FROM diary")
    users_count = cursor.fetchone()[0]

    since = int(time.time()) - 7 * 86400
    cursor.execute("SELECT AVG(score) FROM diary WHERE created_at >= ?", (since,))
    row = cursor.fetchone()
    avg_score = round(row[0], 1) if row and row[0] else None

    conn.close()

    return users_count, avg_score


def reset_user_profile(user_id):
    """Сбрасывает профиль пользователя — для тестирования."""

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
    UPDATE users
    SET anxiety_type=NULL, finished=0, bought=0, thinking=0,
        saw_offer=0, saw_offer_at=NULL, started_quiz=0,
        health_consent=0, health_consent_at=NULL
    WHERE user_id=?
    """, (user_id,))

    cursor.execute("DELETE FROM funnel_tasks WHERE user_id=? AND sent=0", (user_id,))

    conn.commit()
    conn.close()


def has_diary_weekly_task(user_id):

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT COUNT(*) FROM funnel_tasks
    WHERE user_id=? AND message_type='diary_weekly' AND sent=0
    """, (user_id,))
    count = cursor.fetchone()[0]

    conn.close()

    return count > 0


def save_phone(user_id, phone):

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
    UPDATE users SET phone=? WHERE user_id=?
    """, (phone, user_id))

    conn.commit()
    conn.close()


def get_phone(user_id):

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("SELECT phone FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()

    conn.close()

    return row[0] if row and row[0] else None


def save_health_consent(user_id):

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
    UPDATE users SET health_consent=1, health_consent_at=? WHERE user_id=?
    """, (int(time.time()), user_id))

    conn.commit()
    conn.close()


def has_health_consent(user_id):

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("SELECT health_consent FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()

    conn.close()

    return bool(row and row[0])


def update_result(user_id, anxiety_type):

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
    UPDATE users
    SET anxiety_type=?,
        finished=1
    WHERE user_id=?
    """, (anxiety_type, user_id))

    conn.commit()
    conn.close()


def set_thinking(user_id):

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
    UPDATE users
    SET thinking=1
    WHERE user_id=?
    """, (user_id,))

    conn.commit()
    conn.close()


def set_bought(user_id):

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
    UPDATE users
    SET bought=1
    WHERE user_id=?
    """, (user_id,))

    conn.commit()
    conn.close()


def get_users():

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users")

    data = cursor.fetchall()

    conn.close()

    return data


def get_user_ids():

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()

    conn.close()

    return [user[0] for user in users]


def get_subscribed_user_ids():
    """Только те, кто не отписался — для рассылок."""

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("SELECT user_id FROM users WHERE unsubscribed=0 OR unsubscribed IS NULL")
    users = cursor.fetchall()

    conn.close()

    return [user[0] for user in users]


def get_stats():

    conn = connect()
    cursor = conn.cursor()

    stats = {}

    cursor.execute("SELECT COUNT(*) FROM users")
    stats["all_users"] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM users WHERE finished=1")
    stats["finished"] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM users WHERE saw_offer=1")
    stats["saw_offer"] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM users WHERE anxiety_type='A'")
    stats["scanner"] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM users WHERE anxiety_type='B'")
    stats["catastrophist"] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM users WHERE anxiety_type='C'")
    stats["freezer"] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM users WHERE anxiety_type='D'")
    stats["controller"] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM users WHERE bought=1")
    stats["bought"] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM users WHERE thinking=1")
    stats["thinking"] = cursor.fetchone()[0]

    # Источники трафика
    cursor.execute("""
    SELECT source, COUNT(*) as cnt FROM users
    WHERE source IS NOT NULL
    GROUP BY source
    ORDER BY cnt DESC
    LIMIT 10
    """)
    stats["sources"] = cursor.fetchall()

    conn.close()

    return stats


# ---------------- ВОРОНКА ----------------


def has_pending_funnel_tasks(user_id):
    """Проверяет только задачи воронки продаж, не quiz_reminder."""

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT COUNT(*) FROM funnel_tasks
    WHERE user_id=? AND sent=0
    AND message_type IN ('1h', '24h', '72h')
    """, (user_id,))

    count = cursor.fetchone()[0]

    conn.close()

    return count > 0


def has_pending_quiz_reminder(user_id):

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT COUNT(*) FROM funnel_tasks
    WHERE user_id=? AND sent=0 AND message_type='quiz_reminder'
    """, (user_id,))

    count = cursor.fetchone()[0]

    conn.close()

    return count > 0


def add_funnel_task(user_id, delay_seconds, message_type):

    conn = connect()
    cursor = conn.cursor()

    send_at = int(time.time()) + delay_seconds

    cursor.execute("""
    INSERT INTO funnel_tasks
    (user_id, send_at, message_type)
    VALUES (?, ?, ?)
    """, (user_id, send_at, message_type))

    conn.commit()
    conn.close()


def get_pending_tasks():

    conn = connect()
    cursor = conn.cursor()

    now = int(time.time())

    cursor.execute("""
    SELECT id, user_id, message_type
    FROM funnel_tasks
    WHERE sent=0
    AND send_at<=?
    """, (now,))

    tasks = cursor.fetchall()

    conn.close()

    return tasks


def mark_task_sent(task_id):

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
    UPDATE funnel_tasks
    SET sent=1
    WHERE id=?
    """, (task_id,))

    conn.commit()
    conn.close()


def get_ai_history(user_id, limit=20):

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT role, text FROM messages
    WHERE user_id=? AND role IN ('ai_user', 'ai_bot')
    ORDER BY created_at DESC
    LIMIT ?
    """, (user_id, limit))

    rows = cursor.fetchall()

    conn.close()

    # Возвращаем в хронологическом порядке в формате для Claude API
    result = []
    for role, text in reversed(rows):
        result.append({
            "role": "user" if role == "ai_user" else "assistant",
            "content": text
        })

    return result


def save_message(user_id, role, text):

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO messages (user_id, role, text, created_at)
    VALUES (?, ?, ?, ?)
    """, (user_id, role, text, int(time.time())))

    conn.commit()
    conn.close()


def get_history(user_id):

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT role, text, created_at FROM messages
    WHERE user_id=?
    ORDER BY created_at
    """, (user_id,))

    rows = cursor.fetchall()

    conn.close()

    return rows


def get_all_users_data():

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT user_id, username, first_name, last_name, phone,
           anxiety_type, finished, saw_offer, bought, thinking, source
    FROM users
    ORDER BY user_id
    """)

    rows = cursor.fetchall()

    conn.close()

    return rows


def get_user_bought(user_id):

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT bought FROM users WHERE user_id=?
    """, (user_id,))

    row = cursor.fetchone()

    conn.close()

    return bool(row and row[0] == 1)


def save_payment(user_id, payment_id, payment_type="product", payment_url=None):

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO payments (user_id, payment_id, payment_type, payment_url, created_at)
    VALUES (?, ?, ?, ?, ?)
    """, (user_id, payment_id, payment_type, payment_url, int(time.time())))

    conn.commit()
    conn.close()


def get_recent_payment_url(user_id, minutes=30):
    """Возвращает URL существующего платежа если он создан менее N минут назад."""

    conn = connect()
    cursor = conn.cursor()

    since = int(time.time()) - minutes * 60

    cursor.execute("""
    SELECT payment_url FROM payments
    WHERE user_id=? AND payment_url IS NOT NULL AND created_at >= ?
    ORDER BY created_at DESC LIMIT 1
    """, (user_id, since))

    row = cursor.fetchone()
    conn.close()

    return row[0] if row else None


def set_unsubscribed(user_id):

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("UPDATE users SET unsubscribed=1 WHERE user_id=?", (user_id,))

    conn.commit()
    conn.close()


def is_unsubscribed(user_id):

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("SELECT unsubscribed FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()

    conn.close()

    return bool(row and row[0] == 1)


def get_payment_type(payment_id):

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT payment_type FROM payments WHERE payment_id=?
    """, (payment_id,))

    row = cursor.fetchone()

    conn.close()

    return row[0] if row else "product"


def get_latest_payment_id(user_id):

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT payment_id FROM payments
    WHERE user_id=?
    ORDER BY created_at DESC
    LIMIT 1
    """, (user_id,))

    row = cursor.fetchone()

    conn.close()

    return row[0] if row else None


def get_user_type(user_id):

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT anxiety_type
    FROM users
    WHERE user_id=?
    """, (user_id,))

    row = cursor.fetchone()

    conn.close()

    return row[0] if row else None


def has_tip_tasks(user_id):

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT COUNT(*) FROM funnel_tasks
    WHERE user_id=? AND message_type LIKE 'tip_%' AND sent=0
    """, (user_id,))

    count = cursor.fetchone()[0]

    conn.close()

    return count > 0


# ---------------- ДНЕВНИК ----------------


def save_diary_entry(user_id, score, note=None):

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO diary (user_id, score, note, created_at)
    VALUES (?, ?, ?, ?)
    """, (user_id, score, note, int(time.time())))

    diary_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return diary_id


# ---------------- РАЗБОР МЫСЛИ (CBT) ----------------


def save_thought_record(user_id, diary_id, automatic_thought, distortion, reframe, score_before, score_after):

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO thought_records
    (user_id, diary_id, automatic_thought, distortion, reframe, score_before, score_after, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (user_id, diary_id, automatic_thought, distortion, reframe, score_before, score_after, int(time.time())))

    conn.commit()
    conn.close()


def get_thought_record_count(user_id):

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM thought_records WHERE user_id=?", (user_id,))
    count = cursor.fetchone()[0]

    conn.close()

    return count


def get_common_distortion(user_id):
    """Возвращает (искажение, сколько раз встретилось) — самое частое у пользователя, или None."""

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT distortion, COUNT(*) as c FROM thought_records
    WHERE user_id=? AND distortion IS NOT NULL
    GROUP BY distortion
    ORDER BY c DESC
    LIMIT 1
    """, (user_id,))
    row = cursor.fetchone()

    conn.close()

    return row if row else None


def get_diary_history(user_id, days=7):

    conn = connect()
    cursor = conn.cursor()

    since = int(time.time()) - days * 86400

    cursor.execute("""
    SELECT score, note, created_at FROM diary
    WHERE user_id=? AND created_at>=?
    ORDER BY created_at
    """, (user_id, since))

    rows = cursor.fetchall()

    conn.close()

    return rows


# ---------------- ОТЗЫВЫ ----------------


def save_review(user_id, text):

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO reviews (user_id, text, created_at)
    VALUES (?, ?, ?)
    """, (user_id, text, int(time.time())))

    conn.commit()
    conn.close()


def get_reviews(limit=20):

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT r.user_id, u.first_name, u.username, r.text, r.created_at
    FROM reviews r
    LEFT JOIN users u ON r.user_id = u.user_id
    ORDER BY r.created_at DESC
    LIMIT ?
    """, (limit,))

    rows = cursor.fetchall()

    conn.close()

    return rows


# ---------------- ЗАПИСИ НА КОНСУЛЬТАЦИЮ ----------------


def save_booking(user_id, preferred_time, date_str=None, time_str=None):

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO bookings (user_id, preferred_time, created_at, date_str, time_str, status)
    VALUES (?, ?, ?, ?, ?, 'pending')
    """, (user_id, preferred_time, int(time.time()), date_str, time_str))

    conn.commit()
    conn.close()


def is_slot_booked(date_str, time_str):
    """Есть ли уже подтверждённая запись на этот день/время (для защиты от двойного бронирования)."""

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT COUNT(*) FROM bookings
    WHERE date_str=? AND time_str=? AND status='confirmed'
    """, (date_str, time_str))

    count = cursor.fetchone()[0]

    conn.close()

    return count > 0


def mark_booking_confirmed(user_id, date_str, time_str):

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
    UPDATE bookings SET status='confirmed'
    WHERE id = (
        SELECT id FROM bookings
        WHERE user_id=? AND date_str=? AND time_str=? AND status='pending'
        ORDER BY created_at DESC LIMIT 1
    )
    """, (user_id, date_str, time_str))

    conn.commit()
    conn.close()


# ---------------- РЕФЕРАЛЫ ----------------


def save_user_referral(user_id, referrer_id):

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
    UPDATE users SET referred_by=? WHERE user_id=? AND referred_by IS NULL
    """, (referrer_id, user_id))

    cursor.execute("""
    UPDATE users SET referral_count = referral_count + 1 WHERE user_id=?
    """, (referrer_id,))

    conn.commit()
    conn.close()


def get_referral_count(user_id):

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT referral_count FROM users WHERE user_id=?
    """, (user_id,))

    row = cursor.fetchone()

    conn.close()

    return row[0] if row else 0


def set_started_quiz(user_id):

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("UPDATE users SET started_quiz=1 WHERE user_id=?", (user_id,))

    conn.commit()
    conn.close()


def get_funnel_stats():

    conn = connect()
    cursor = conn.cursor()

    stats = {}

    cursor.execute("SELECT COUNT(*) FROM users")
    stats["all_users"] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM users WHERE started_quiz=1")
    stats["started_quiz"] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM users WHERE finished=1")
    stats["finished"] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM users WHERE saw_offer=1")
    stats["saw_offer"] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM users WHERE bought=1")
    stats["bought"] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM bookings")
    stats["bookings"] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM payments WHERE payment_type='product'")
    stats["paid_product"] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM payments WHERE payment_type='booking'")
    stats["paid_booking"] = cursor.fetchone()[0]

    stats["revenue"] = stats["paid_product"] * PRODUCT_PRICE + stats["paid_booking"] * SESSION_PRICE

    cursor.execute("SELECT COALESCE(SUM(referral_count), 0) FROM users")
    stats["referrals"] = cursor.fetchone()[0]

    conn.close()

    return stats