import sqlite3
import time

from config import PRODUCT_PRICE, SESSION_PRICE


def connect():
    return sqlite3.connect("users.db")


# Этапы воронки CRM — единый источник правды (ключ хранится в users.crm_stage,
# русская подпись только для отображения; переименование подписи не должно
# ломать авто-определение этапа, поэтому ключи английские и стабильные).
CRM_STAGES = [
    ("new_lead", "Новый лид"),
    ("in_quiz", "Проходит тест"),
    ("thinking", "Увидел оффер / думает"),
    ("bought", "Купил разбор"),
    ("booking", "Запись на сессию"),
    ("client", "Был на сессии"),
    ("inactive", "Неактивен"),
]


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

    # CRM-панель листает переписку одного клиента (WHERE user_id ORDER BY id)
    # и считает последнюю активность по MAX(created_at) для каждого клиента —
    # без индекса это полный проход по всей истории всех диалогов.
    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_messages_user_id
    ON messages (user_id, id)
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

    # история результатов квиза (users.anxiety_type хранит только последний —
    # эта таблица нужна для истории в личном кабинете, пишется в дополнение)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS quiz_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        anxiety_type TEXT,
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

    # закрытые админом даты/слоты записи (NULL time_str = закрыт весь день)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS blocked_slots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date_str TEXT NOT NULL,
        time_str TEXT,
        created_at INTEGER
    )
    """)

    # рефералы

    for col in ["referred_by INTEGER", "referral_count INTEGER DEFAULT 0",
                "unsubscribed INTEGER DEFAULT 0"]:
        try:
            cursor.execute(f"ALTER TABLE users ADD COLUMN {col}")
        except Exception:
            pass

    # CRM: ручной этап воронки (NULL = используем авто-определение по
    # существующим полям, см. crm_stage_for) и когда он в последний раз менялся

    for col in ["crm_stage TEXT", "crm_stage_updated_at INTEGER"]:
        try:
            cursor.execute(f"ALTER TABLE users ADD COLUMN {col}")
        except Exception:
            pass

    # CRM: заметки о клиенте, с опциональным напоминанием (reminder_at NULL —
    # обычная заметка без напоминания)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS crm_notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        text TEXT,
        created_at INTEGER,
        reminder_at INTEGER,
        reminder_done INTEGER DEFAULT 0,
        notified INTEGER DEFAULT 0
    )
    """)

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


def save_quiz_result(user_id, anxiety_type):
    """Пишется рядом с update_result — не заменяет users.anxiety_type,
    а копит историю прохождений для личного кабинета."""

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO quiz_results (user_id, anxiety_type, created_at)
    VALUES (?, ?, ?)
    """, (user_id, anxiety_type, int(time.time())))

    conn.commit()
    conn.close()


def get_quiz_result_latest(user_id):
    """Возвращает (anxiety_type, created_at) последнего прохождения или None."""

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT anxiety_type, created_at FROM quiz_results
    WHERE user_id=? ORDER BY created_at DESC, id DESC LIMIT 1
    """, (user_id,))

    row = cursor.fetchone()
    conn.close()

    return row if row else None


def get_quiz_result_history(user_id, limit=20):
    """Возвращает список (anxiety_type, created_at) от новых к старым."""

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT anxiety_type, created_at FROM quiz_results
    WHERE user_id=? ORDER BY created_at DESC, id DESC LIMIT ?
    """, (user_id, limit))

    rows = cursor.fetchall()
    conn.close()

    return rows


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


def get_recent_payment_url(user_id, payment_type="product", minutes=30):
    """Возвращает URL существующего платежа того же типа, если он создан
    менее N минут назад (тип обязателен, иначе можно вернуть, например,
    ссылку на сессию вместо ссылки на продукт)."""

    conn = connect()
    cursor = conn.cursor()

    since = int(time.time()) - minutes * 60

    cursor.execute("""
    SELECT payment_url FROM payments
    WHERE user_id=? AND payment_type=? AND payment_url IS NOT NULL AND created_at >= ?
    ORDER BY created_at DESC LIMIT 1
    """, (user_id, payment_type, since))

    row = cursor.fetchone()
    conn.close()

    return row[0] if row else None


def get_payment_owner(payment_id):
    """Возвращает user_id владельца платежа или None — проверка доступа перед
    тем как отдать статус платежа по API."""

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("SELECT user_id FROM payments WHERE payment_id=?", (payment_id,))

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

    # id DESC как вторичный ключ — при двух платежах в одну секунду (Unix-время,
    # секундная точность) сортировка только по created_at даёт непредсказуемый tie-break.
    cursor.execute("""
    SELECT payment_id FROM payments
    WHERE user_id=?
    ORDER BY created_at DESC, id DESC
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


def mark_booking_declined(user_id, date_str, time_str):

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
    UPDATE bookings SET status='declined'
    WHERE id = (
        SELECT id FROM bookings
        WHERE user_id=? AND date_str=? AND time_str=? AND status='pending'
        ORDER BY created_at DESC LIMIT 1
    )
    """, (user_id, date_str, time_str))

    conn.commit()
    conn.close()


def get_user_bookings(user_id, limit=10):
    """Возвращает записи пользователя (date_str, time_str, status, created_at)
    от новых к старым — для личного кабинета."""

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT date_str, time_str, status, created_at FROM bookings
    WHERE user_id=? ORDER BY created_at DESC, id DESC LIMIT ?
    """, (user_id, limit))

    rows = cursor.fetchall()
    conn.close()

    return rows


def get_taken_times(date_str):
    """Времена на дату, уже занятые бронированиями (pending или confirmed) —
    чтобы не показывать клиентам слот, который кто-то уже запросил."""

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT time_str FROM bookings
    WHERE date_str=? AND status IN ('pending', 'confirmed')
    """, (date_str,))

    rows = [r[0] for r in cursor.fetchall()]

    conn.close()

    return rows


# ---------------- ЗАКРЫТЫЕ АДМИНОМ ДАТЫ/СЛОТЫ ----------------


def is_date_fully_blocked(date_str):

    conn = connect()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT COUNT(*) FROM blocked_slots WHERE date_str=? AND time_str IS NULL",
        (date_str,)
    )
    count = cursor.fetchone()[0]

    conn.close()

    return count > 0


def get_blocked_times(date_str):
    """Конкретные закрытые админом времена на дату (без учёта блокировки всего дня)."""

    conn = connect()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT time_str FROM blocked_slots WHERE date_str=? AND time_str IS NOT NULL",
        (date_str,)
    )
    rows = [r[0] for r in cursor.fetchall()]

    conn.close()

    return rows


def get_blocked_dates(start_date_str, end_date_str):
    """Даты (закрытые целиком), попадающие в диапазон [start, end] — для отрисовки календаря
    одним запросом на месяц вместо запроса на каждый день."""

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT date_str FROM blocked_slots
    WHERE time_str IS NULL AND date_str BETWEEN ? AND ?
    """, (start_date_str, end_date_str))
    rows = {r[0] for r in cursor.fetchall()}

    conn.close()

    return rows


def toggle_blocked_time(date_str, time_str):
    """Переключает блокировку конкретного времени на дату. Возвращает True, если теперь закрыто."""

    conn = connect()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id FROM blocked_slots WHERE date_str=? AND time_str=?",
        (date_str, time_str)
    )
    row = cursor.fetchone()

    if row:
        cursor.execute("DELETE FROM blocked_slots WHERE id=?", (row[0],))
        result = False
    else:
        cursor.execute(
            "INSERT INTO blocked_slots (date_str, time_str, created_at) VALUES (?, ?, ?)",
            (date_str, time_str, int(time.time()))
        )
        result = True

    conn.commit()
    conn.close()

    return result


def toggle_blocked_day(date_str):
    """Переключает блокировку всего дня. Возвращает True, если теперь закрыт.
    При закрытии дня точечные блокировки времени на эту дату больше не нужны — чистим их."""

    conn = connect()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id FROM blocked_slots WHERE date_str=? AND time_str IS NULL",
        (date_str,)
    )
    row = cursor.fetchone()

    if row:
        cursor.execute("DELETE FROM blocked_slots WHERE id=?", (row[0],))
        result = False
    else:
        cursor.execute("DELETE FROM blocked_slots WHERE date_str=? AND time_str IS NOT NULL", (date_str,))
        cursor.execute(
            "INSERT INTO blocked_slots (date_str, time_str, created_at) VALUES (?, NULL, ?)",
            (date_str, int(time.time()))
        )
        result = True

    conn.commit()
    conn.close()

    return result


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


# ---------------- CRM ----------------


def get_user_payments(user_id):
    """Возвращает (payment_id, payment_type, created_at, payment_url)
    от новых к старым."""

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT payment_id, payment_type, created_at, payment_url FROM payments
    WHERE user_id=? ORDER BY created_at DESC, id DESC
    """, (user_id,))

    rows = cursor.fetchall()
    conn.close()

    return rows


def _crm_stage_for(started_quiz, finished, bought, latest_booking_status,
                    latest_booking_date, today_str):
    """Авто-определение этапа воронки по существующим полям — используется,
    когда users.crm_stage не выставлен вручную (NULL). Последняя запись
    'confirmed' с прошедшей датой считается уже отработанной сессией."""

    if latest_booking_status == "pending":
        return "booking"

    if latest_booking_status == "confirmed":
        if latest_booking_date and latest_booking_date < today_str:
            return "client"
        return "booking"

    # latest_booking_status в ("declined", None) — записи либо не было,
    # либо отклонена, дальше смотрим на общий прогресс по тесту/оплате

    if bought:
        return "bought"

    if finished:
        return "thinking"

    if started_quiz:
        return "in_quiz"

    return "new_lead"


def get_crm_client_list(search=None):
    """Список клиентов для канбана/таблицы: профиль + авто/ручной этап +
    последняя активность. search фильтруется в Python (регистронезависимо),
    а не через SQL LIKE/COLLATE NOCASE — у SQLite нет таблицы регистров для
    кириллицы без ICU-расширения, так что 'бор' не находил бы 'Борис'. Для
    практики одного психолога (не тысячи строк) это не проблема с
    производительностью."""

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT u.user_id, u.username, u.first_name, u.last_name, u.anxiety_type,
           u.bought, u.started_quiz, u.finished, u.crm_stage, u.crm_stage_updated_at,
           (SELECT MAX(created_at) FROM messages m WHERE m.user_id = u.user_id) AS last_activity_at,
           (SELECT status FROM bookings b WHERE b.user_id = u.user_id
            ORDER BY b.created_at DESC, b.id DESC LIMIT 1) AS latest_booking_status,
           (SELECT date_str FROM bookings b WHERE b.user_id = u.user_id
            ORDER BY b.created_at DESC, b.id DESC LIMIT 1) AS latest_booking_date
    FROM users u
    ORDER BY last_activity_at DESC
    """)

    rows = cursor.fetchall()
    conn.close()

    today_str = time.strftime("%Y%m%d")
    search_lower = search.lower() if search else None

    clients = []
    for (user_id, username, first_name, last_name, anxiety_type, bought,
         started_quiz, finished, crm_stage, crm_stage_updated_at, last_activity_at,
         latest_booking_status, latest_booking_date) in rows:

        if search_lower:
            haystack = " ".join(filter(None, [username, first_name, last_name])).lower()
            if search_lower not in haystack:
                continue

        stage = crm_stage or _crm_stage_for(
            started_quiz, finished, bought, latest_booking_status,
            latest_booking_date, today_str
        )
        clients.append({
            "user_id": user_id,
            "username": username,
            "first_name": first_name,
            "last_name": last_name,
            "anxiety_type": anxiety_type,
            "bought": bool(bought),
            "stage": stage,
            "stage_is_manual": crm_stage is not None,
            "stage_updated_at": crm_stage_updated_at,
            "last_activity_at": last_activity_at,
        })

    return clients


def get_crm_client_detail(user_id):
    """Полная карточка клиента для CRM: профиль + записи + платежи + дневник
    + история теста + заметки — один словарь на все нужды карточки."""

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT user_id, username, first_name, last_name, phone, anxiety_type,
           finished, bought, thinking, source, crm_stage, crm_stage_updated_at,
           started_quiz
    FROM users WHERE user_id=?
    """, (user_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    (uid, username, first_name, last_name, phone, anxiety_type, finished,
     bought, thinking, source, crm_stage, crm_stage_updated_at,
     started_quiz) = row

    bookings = [
        {"date_str": d, "time_str": t, "status": s, "created_at": c}
        for d, t, s, c in get_user_bookings(user_id, limit=50)
    ]

    # Этап считаем так же, как в списке (get_crm_client_list): при NULL в
    # crm_stage — авто-определение. Иначе селект в карточке показывал бы
    # «Новый лид» для всех, кому этап не выставляли руками, и расходился бы
    # с колонкой канбана, откуда карточку и открыли.
    stage = crm_stage or _crm_stage_for(
        started_quiz, finished, bought,
        bookings[0]["status"] if bookings else None,
        bookings[0]["date_str"] if bookings else None,
        time.strftime("%Y%m%d"),
    )

    return {
        "user_id": uid,
        "username": username,
        "first_name": first_name,
        "last_name": last_name,
        "phone": phone,
        "anxiety_type": anxiety_type,
        "finished": bool(finished),
        "bought": bool(bought),
        "thinking": bool(thinking),
        "source": source,
        "stage": stage,
        "stage_is_manual": crm_stage is not None,
        "stage_updated_at": crm_stage_updated_at,
        "bookings": bookings,
        "payments": [
            {"payment_id": pid, "payment_type": pt, "created_at": c, "payment_url": url}
            for pid, pt, c, url in get_user_payments(user_id)
        ],
        "diary": [
            {"score": score, "note": note, "created_at": c}
            for score, note, c in get_diary_history(user_id, days=365)
        ],
        "quiz_history": [
            {"anxiety_type": t, "created_at": c}
            for t, c in get_quiz_result_history(user_id, limit=50)
        ],
        "notes": get_crm_notes(user_id),
    }


def get_crm_dialog(user_id, limit=50, before_id=None):
    """Порция диалога для CRM-панели, в хронологическом порядке.

    Листаем от новых к старым: без before_id отдаём последние `limit`
    сообщений, с before_id — следующую порцию строго старше уже загруженных
    ("показать раньше"). Сортировка по id, а не по created_at: соседние
    сообщения диалога часто попадают в одну и ту же секунду, и по времени
    их порядок неустойчив.

    has_more считаем, запросив на одну строку больше лимита — так фронт
    знает, показывать ли кнопку догрузки, без второго COUNT-запроса.
    """

    conn = connect()
    cursor = conn.cursor()

    if before_id:
        cursor.execute("""
        SELECT id, role, text, created_at FROM messages
        WHERE user_id=? AND id<?
        ORDER BY id DESC LIMIT ?
        """, (user_id, before_id, limit + 1))
    else:
        cursor.execute("""
        SELECT id, role, text, created_at FROM messages
        WHERE user_id=?
        ORDER BY id DESC LIMIT ?
        """, (user_id, limit + 1))

    rows = cursor.fetchall()
    conn.close()

    has_more = len(rows) > limit

    return {
        "messages": [
            {"id": mid, "role": role, "text": text, "created_at": c}
            for mid, role, text, c in reversed(rows[:limit])
        ],
        "has_more": has_more,
    }


def set_crm_stage(user_id, stage_key):

    conn = connect()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE users SET crm_stage=?, crm_stage_updated_at=? WHERE user_id=?",
        (stage_key, int(time.time()), user_id)
    )

    conn.commit()
    conn.close()


def add_crm_note(user_id, text, reminder_at=None):

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO crm_notes (user_id, text, created_at, reminder_at)
    VALUES (?, ?, ?, ?)
    """, (user_id, text, int(time.time()), reminder_at))

    conn.commit()
    conn.close()


def get_crm_notes(user_id):
    """Возвращает список словарей — заметки клиента, новые сверху."""

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT id, text, created_at, reminder_at, reminder_done FROM crm_notes
    WHERE user_id=? ORDER BY created_at DESC, id DESC
    """, (user_id,))

    rows = cursor.fetchall()
    conn.close()

    return [
        {"id": i, "text": t, "created_at": c, "reminder_at": r, "reminder_done": bool(d)}
        for i, t, c, r, d in rows
    ]


def complete_crm_reminder(note_id):

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("UPDATE crm_notes SET reminder_done=1 WHERE id=?", (note_id,))

    conn.commit()
    conn.close()


def get_due_reminders():
    """Напоминания, срок которых наступил и о которых ещё не сообщили админу.
    Возвращает (id, user_id, text, reminder_at)."""

    conn = connect()
    cursor = conn.cursor()

    now = int(time.time())
    cursor.execute("""
    SELECT id, user_id, text, reminder_at FROM crm_notes
    WHERE reminder_at IS NOT NULL AND reminder_at<=? AND notified=0
    """, (now,))

    rows = cursor.fetchall()
    conn.close()

    return rows


def mark_reminder_notified(note_id):

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("UPDATE crm_notes SET notified=1 WHERE id=?", (note_id,))

    conn.commit()
    conn.close()