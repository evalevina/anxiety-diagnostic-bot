import io
import logging
import os
import asyncio

from aiogram import Router, F
from aiogram.fsm.context import FSMContext

logger = logging.getLogger(__name__)
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    BufferedInputFile,
    FSInputFile
)
from aiogram.filters import Command
import openpyxl

from database import (
    get_stats,
    get_user_ids,
    get_subscribed_user_ids,
    get_all_users_data,
    set_bought,
    set_thinking,
    get_reviews,
    reset_user_profile,
    get_diary_stats,
    get_funnel_stats
)
from config import ADMIN_ID

router = Router()


# ---------- КНОПКИ ----------

admin_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[

        [
            InlineKeyboardButton(
                text="📊 Статистика",
                callback_data="admin_stats"
            ),

            InlineKeyboardButton(
                text="👥 Пользователи",
                callback_data="admin_users"
            )
        ],

        [
            InlineKeyboardButton(
                text="📢 Рассылка",
                callback_data="admin_broadcast"
            ),

            InlineKeyboardButton(
                text="💳 Покупка",
                callback_data="admin_buy"
            )
        ],

        [
            InlineKeyboardButton(
                text="🤔 Думает",
                callback_data="admin_thinking"
            ),

            InlineKeyboardButton(
                text="🔄 Обновить",
                callback_data="admin_refresh"
            )
        ],

        [
            InlineKeyboardButton(
                text="📥 Выгрузить Excel",
                callback_data="admin_export"
            ),
            InlineKeyboardButton(
                text="💾 Бэкап БД",
                callback_data="admin_backup"
            )
        ],

        [
            InlineKeyboardButton(
                text="⭐ Отзывы",
                callback_data="admin_reviews"
            ),
            InlineKeyboardButton(
                text="📈 Воронка",
                callback_data="admin_funnel"
            )
        ],

        [
            InlineKeyboardButton(
                text="🎯 Рассылка по типу",
                callback_data="admin_broadcast_type"
            )
        ],

        [
            InlineKeyboardButton(
                text="📅 Календарь записи",
                callback_data="admin_calendar"
            )
        ]
    ]
)


# ---------- АДМИН ПАНЕЛЬ ----------

@router.message(Command("admin"))
async def admin_panel(message: Message):

    if message.from_user.id != ADMIN_ID:
        return

    await message.answer(
        "⚙️ Админ-панель",
        reply_markup=admin_keyboard
    )


# ---------- СТАТИСТИКА ----------

@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):

    if callback.from_user.id != ADMIN_ID:
        return

    stats = get_stats()

    all_u = stats["all_users"]
    finished = stats["finished"]
    saw_offer = stats["saw_offer"]
    bought = stats["bought"]

    def pct(part, total):
        return f"{round(part / total * 100)}%" if total else "—"

    sources_text = ""
    if stats.get("sources"):
        sources_text = "\n\n📌 Источники:\n" + "\n".join(
            f"  {src or 'прямой'}: {cnt}" for src, cnt in stats["sources"]
        )

    text = (
        "📊 Статистика бота\n\n"

        f"👥 Всего: {all_u}\n"
        f"✅ Прошли тест: {finished} ({pct(finished, all_u)})\n"
        f"👀 Увидели оффер: {saw_offer} ({pct(saw_offer, all_u)})\n"
        f"💳 Купили: {bought} ({pct(bought, saw_offer)})\n"
        f"🤔 Думают: {stats['thinking']}\n\n"

        f"Типы тревоги:\n"
        f"🔍 Сканер: {stats['scanner']}\n"
        f"🌪 Катастрофист: {stats['catastrophist']}\n"
        f"🌫 Замиратель: {stats['freezer']}\n"
        f"🎯 Контролёр: {stats['controller']}"

        f"{sources_text}"
    )

    diary_users, diary_avg = get_diary_stats()
    avg_text = f"{diary_avg}/10" if diary_avg else "нет данных"
    text += f"\n\n📔 Дневник тревоги:\nВедут дневник: {diary_users} чел.\nСредняя тревога (7 дней): {avg_text}"

    await callback.message.answer(text)
    await callback.answer()


# ---------- ПОЛЬЗОВАТЕЛИ ----------

@router.callback_query(F.data == "admin_users")
async def admin_users(callback: CallbackQuery):

    if callback.from_user.id != ADMIN_ID:
        return

    users = get_user_ids()

    if not users:
        await callback.message.answer("👥 Пользователей пока нет")
        await callback.answer()
        return

    # Telegram режет сообщения на 4096 символов — при росте базы список
    # одним сообщением рано или поздно перестанет отправляться. Бьём на
    # порции по 200 ID (для больших выгрузок всё равно лучше Excel).
    chunk_size = 200
    total = len(users)
    for i in range(0, total, chunk_size):
        chunk = users[i:i + chunk_size]
        if total > chunk_size:
            header = f"👥 Пользователи ({i + 1}–{i + len(chunk)} из {total}):\n\n"
        else:
            header = f"👥 Пользователи ({total}):\n\n"
        await callback.message.answer(header + "\n".join(str(u) for u in chunk))

    await callback.answer()


# ---------- РАССЫЛКА ----------

@router.message(Command("broadcast"))
async def broadcast(message: Message):

    if message.from_user.id != ADMIN_ID:
        return

    text = message.text.replace("/broadcast", "").strip()

    if not text:
        await message.answer(
            "Пример:\n\n"
            "/broadcast Всем привет 🤍"
        )
        return

    users = get_subscribed_user_ids()

    sent = 0

    for user_id in users:

        try:

            await message.bot.send_message(
                chat_id=user_id,
                text=text
            )

            sent += 1

        except Exception as e:

            logger.warning(f"Рассылка: ошибка для user_id={user_id}: {e}")

        await asyncio.sleep(0.05)

    await message.answer(
        f"✅ Отправлено: {sent}"
    )


# ---------- ОТМЕТИТЬ ПОКУПКУ ----------

@router.message(Command("buy"))
async def mark_bought(message: Message):

    if message.from_user.id != ADMIN_ID:
        return

    try:

        user_id = int(
            message.text.replace("/buy", "").strip()
        )

        set_bought(user_id)

        await message.answer(
            f"💳 Покупка отмечена\n\nID: {user_id}"
        )

    except Exception:

        await message.answer(
            "Пример:\n\n"
            "/buy 6809939303"
        )


# ---------- ОТМЕТИТЬ ДУМАЕТ ----------

@router.message(Command("thinking"))
async def mark_thinking(message: Message):

    if message.from_user.id != ADMIN_ID:
        return

    try:

        user_id = int(
            message.text.replace("/thinking", "").strip()
        )

        set_thinking(user_id)

        await message.answer(
            f"🤔 Пользователь отмечен как думающий\n\nID: {user_id}"
        )

    except Exception:

        await message.answer(
            "Пример:\n\n"
            "/thinking 6809939303"
        )
        # ---------- РАССЫЛКА ----------

@router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast(callback: CallbackQuery):

    if callback.from_user.id != ADMIN_ID:
        return

    await callback.message.answer(
        "Используй команду:\n\n"
        "/broadcast Текст рассылки"
    )

    await callback.answer()


# ---------- ПОКУПКА ----------

@router.callback_query(F.data == "admin_buy")
async def admin_buy(callback: CallbackQuery):

    if callback.from_user.id != ADMIN_ID:
        return

    await callback.message.answer(
        "Используй:\n\n"
        "/buy ID_пользователя"
    )

    await callback.answer()


# ---------- ДУМАЕТ ----------

@router.callback_query(F.data == "admin_thinking")
async def admin_thinking(callback: CallbackQuery):

    if callback.from_user.id != ADMIN_ID:
        return

    await callback.message.answer(
        "Используй:\n\n"
        "/thinking ID_пользователя"
    )

    await callback.answer()


# ---------- ОБНОВИТЬ ----------

@router.callback_query(F.data == "admin_refresh")
async def admin_refresh(callback: CallbackQuery):

    if callback.from_user.id != ADMIN_ID:
        return

    await callback.message.answer(
        "🔄 Панель обновлена",
        reply_markup=admin_keyboard
    )

    await callback.answer()


# ---------- ЭКСПОРТ EXCEL ----------

ANXIETY_NAMES = {
    "A": "Сканер",
    "B": "Катастрофист",
    "C": "Замиратель",
    "D": "Контролёр"
}


@router.callback_query(F.data == "admin_export")
async def admin_export(callback: CallbackQuery):

    if callback.from_user.id != ADMIN_ID:
        return

    users = get_all_users_data()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Клиенты"

    ws.append([
        "ID", "Ник", "Имя", "Фамилия", "Телефон",
        "Тип тревоги", "Прошёл тест", "Увидел оффер", "Купил", "Думает", "Источник"
    ])

    for row in users:
        user_id, username, first_name, last_name, phone, \
            anxiety_type, finished, saw_offer, bought, thinking, source = row

        ws.append([
            user_id,
            f"@{username}" if username else "",
            first_name or "",
            last_name or "",
            phone or "",
            ANXIETY_NAMES.get(anxiety_type, "") if anxiety_type else "",
            "Да" if finished else "Нет",
            "Да" if saw_offer else "Нет",
            "Да" if bought else "Нет",
            "Да" if thinking else "Нет",
            source or "",
        ])

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    file = BufferedInputFile(buffer.getvalue(), filename="clients.xlsx")

    await callback.message.answer_document(
        file,
        caption=f"📊 База клиентов — {len(users)} чел."
    )

    await callback.answer()


# ---------- БЭКАП БД ----------

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@router.message(Command("backup"))
async def cmd_backup(message: Message):

    if message.from_user.id != ADMIN_ID:
        return

    db_path = os.path.join(BASE_DIR, "users.db")

    if not os.path.exists(db_path):
        await message.answer("Файл базы данных не найден.")
        return

    await message.answer_document(
        FSInputFile(db_path, filename="users_backup.db"),
        caption="💾 Резервная копия базы данных"
    )


@router.callback_query(F.data == "admin_backup")
async def admin_backup(callback: CallbackQuery):

    if callback.from_user.id != ADMIN_ID:
        return

    db_path = os.path.join(BASE_DIR, "users.db")

    if not os.path.exists(db_path):
        await callback.message.answer("Файл базы данных не найден.")
        await callback.answer()
        return

    await callback.message.answer_document(
        FSInputFile(db_path, filename="users_backup.db"),
        caption="💾 Резервная копия базы данных"
    )

    await callback.answer()


# ---------- СБРОС ПРОФИЛЯ (ТЕСТ) ----------

@router.message(Command("reset_me"))
async def reset_me(message: Message, state: FSMContext):

    if message.from_user.id != ADMIN_ID:
        return

    await state.clear()
    reset_user_profile(message.from_user.id)

    await message.answer(
        "✅ Профиль сброшен.\n\n"
        "Теперь ты — новый пользователь.\n"
        "Напиши /start чтобы проверить бота с нуля."
    )


# ---------- РАССЫЛКА ПО ТИПУ ----------

@router.callback_query(F.data == "admin_broadcast_type")
async def admin_broadcast_type_info(callback: CallbackQuery):

    if callback.from_user.id != ADMIN_ID:
        return

    await callback.message.answer(
        "🎯 Рассылка по типу тревоги:\n\n"
        "/broadcast_type A текст — только Сканерам 🔍\n"
        "/broadcast_type B текст — только Катастрофистам 🌪\n"
        "/broadcast_type C текст — только Замирателям 🌫\n"
        "/broadcast_type D текст — только Контролёрам 🎯"
    )

    await callback.answer()


@router.message(Command("broadcast_type"))
async def broadcast_by_type(message: Message):

    if message.from_user.id != ADMIN_ID:
        return

    args = message.text.replace("/broadcast_type", "").strip()

    if len(args) < 3:
        await message.answer(
            "Пример:\n\n"
            "/broadcast_type A Привет, Сканеры! 🔍\n\n"
            "Типы: A (Сканер), B (Катастрофист), C (Замиратель), D (Контролёр)"
        )
        return

    anxiety_type = args[0].upper()
    text = args[1:].strip()

    if anxiety_type not in ("A", "B", "C", "D"):
        await message.answer("Тип должен быть A, B, C или D")
        return

    if not text:
        await message.answer("Текст сообщения не может быть пустым")
        return

    from database import get_user_ids_by_type, is_unsubscribed
    all_users = get_user_ids_by_type(anxiety_type)
    users = [u for u in all_users if not is_unsubscribed(u)]

    type_names = {"A": "Сканер", "B": "Катастрофист", "C": "Замиратель", "D": "Контролёр"}
    await message.answer(f"Отправляю {len(users)} пользователям ({type_names[anxiety_type]})...")

    sent = 0
    for user_id in users:
        try:
            await message.bot.send_message(chat_id=user_id, text=text)
            sent += 1
        except Exception:
            pass
        await asyncio.sleep(0.05)

    await message.answer(f"✅ Отправлено: {sent} из {len(users)}")


# ---------- ОТЗЫВЫ ----------

@router.callback_query(F.data == "admin_reviews")
async def admin_reviews(callback: CallbackQuery):

    if callback.from_user.id != ADMIN_ID:
        return

    reviews = get_reviews(limit=20)

    if not reviews:
        await callback.message.answer("Отзывов пока нет.")
        await callback.answer()
        return

    from datetime import datetime

    text = f"⭐ Последние отзывы ({len(reviews)}):\n\n"

    for user_id, first_name, username, review_text, ts in reviews:
        dt = datetime.fromtimestamp(ts).strftime("%d.%m.%Y")
        user_label = first_name or ""
        if username:
            user_label += f" @{username}"
        text += f"[{dt}] {user_label}:\n{review_text}\n\n"
        text += "─" * 20 + "\n\n"

    if len(text) > 4000:
        for chunk in [text[i:i+4000] for i in range(0, len(text), 4000)]:
            await callback.message.answer(chunk)
    else:
        await callback.message.answer(text)

    await callback.answer()


# ---------- ВОРОНКА ----------

@router.callback_query(F.data == "admin_funnel")
async def admin_funnel(callback: CallbackQuery):

    if callback.from_user.id != ADMIN_ID:
        return

    s = get_funnel_stats()

    def pct(part, total):
        return f"{round(part / total * 100)}%" if total else "—"

    text = (
        "📈 Воронка\n\n"
        f"👥 Зашли в бота:       {s['all_users']}\n"
        f"▶️ Начали тест:        {s['started_quiz']}  ({pct(s['started_quiz'], s['all_users'])})\n"
        f"✅ Прошли тест:        {s['finished']}  ({pct(s['finished'], s['all_users'])})\n"
        f"👀 Увидели оффер:      {s['saw_offer']}  ({pct(s['saw_offer'], s['all_users'])})\n"
        f"💳 Купили (1490₽):    {s['bought']}  ({pct(s['bought'], s['saw_offer'])} от оффера)\n\n"
        f"📋 Записей на сессию:  {s['bookings']}\n"
        f"💰 Выручка:  ~{s['revenue']}₽\n"
        f"👫 Рефералов приведено: {s['referrals']}"
    )

    await callback.message.answer(text)
    await callback.answer()