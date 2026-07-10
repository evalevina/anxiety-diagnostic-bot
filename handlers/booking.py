import asyncio
import calendar
import logging
from datetime import date, timedelta

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
)

from states.quiz_states import BookingState
from database import save_booking, get_user_type, is_slot_booked, mark_booking_confirmed
from yookassa_payment import create_payment_amount
from config import ADMIN_ID, SESSION_PRICE

booking_router = Router()
logger = logging.getLogger(__name__)

SLOTS = ["10:00", "11:00", "12:00", "14:00", "15:00", "16:00", "17:00", "18:00"]

MONTH_NOM = {
    1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
    5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
    9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"
}

MONTH_GEN = {
    1: "января", 2: "февраля", 3: "марта", 4: "апреля",
    5: "мая", 6: "июня", 7: "июля", 8: "августа",
    9: "сентября", 10: "октября", 11: "ноября", 12: "декабря"
}

DAY_NAMES = ["понедельник", "вторник", "среду", "четверг", "пятницу", "субботу"]

TYPE_NAMES = {
    "A": "🔍 Сканер",
    "B": "🌪 Катастрофист",
    "C": "🌫 Замиратель",
    "D": "🎯 Контролёр",
}


def _calendar_kb(year: int, month: int) -> InlineKeyboardMarkup:
    today = date.today()
    max_date = today + timedelta(days=60)

    prev = date(year, month, 1) - timedelta(days=1)
    nxt_first = (date(year, month, 28) + timedelta(days=4)).replace(day=1)

    rows = []

    # Navigation row
    nav = []
    if (year, month) > (today.year, today.month):
        nav.append(InlineKeyboardButton(text="←", callback_data=f"bk_m_{prev.year}{prev.month:02d}"))
    else:
        nav.append(InlineKeyboardButton(text=" ", callback_data="bk_noop"))

    nav.append(InlineKeyboardButton(text=f"{MONTH_NOM[month]} {year}", callback_data="bk_noop"))

    if nxt_first <= max_date.replace(day=1):
        nav.append(InlineKeyboardButton(text="→", callback_data=f"bk_m_{nxt_first.year}{nxt_first.month:02d}"))
    else:
        nav.append(InlineKeyboardButton(text=" ", callback_data="bk_noop"))

    rows.append(nav)

    # Weekday headers (Mon-Sat only)
    rows.append([
        InlineKeyboardButton(text=d, callback_data="bk_noop")
        for d in ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб"]
    ])

    # Weeks
    for week in calendar.monthcalendar(year, month):
        row = []
        for i in range(6):  # Mon=0 to Sat=5, skip Sun=6
            day_num = week[i]
            if day_num == 0:
                row.append(InlineKeyboardButton(text=" ", callback_data="bk_noop"))
            else:
                d = date(year, month, day_num)
                if d <= today or d > max_date:
                    row.append(InlineKeyboardButton(text="·", callback_data="bk_noop"))
                else:
                    row.append(InlineKeyboardButton(
                        text=str(day_num),
                        callback_data=f"bk_d_{year}{month:02d}{day_num:02d}"
                    ))
        rows.append(row)

    return InlineKeyboardMarkup(inline_keyboard=rows)


def _time_kb(date_str: str) -> InlineKeyboardMarkup:
    rows = []
    row = []
    for slot in SLOTS:
        row.append(InlineKeyboardButton(text=slot, callback_data=f"bk_t_{date_str}_{slot}"))
        if len(row) == 4:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="← Другой день", callback_data="bk_back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ── Entry point ──────────────────────────────────────────────────────────────

@booking_router.message(F.text == "📅 Записаться")
async def cmd_booking(message: Message, state: FSMContext):
    await state.clear()
    today = date.today()
    await message.answer(
        "📅 Выбери удобную дату:\n_(доступны ближайшие 60 дней, Пн–Сб)_",
        parse_mode="Markdown",
        reply_markup=_calendar_kb(today.year, today.month)
    )


# ── Calendar navigation ───────────────────────────────────────────────────────

@booking_router.callback_query(F.data.startswith("bk_m_"))
async def navigate_month(callback: CallbackQuery):
    ym = callback.data[5:]
    year, month = int(ym[:4]), int(ym[4:])
    await callback.message.edit_reply_markup(reply_markup=_calendar_kb(year, month))
    await callback.answer()


@booking_router.callback_query(F.data == "bk_noop")
async def noop(callback: CallbackQuery):
    await callback.answer()


@booking_router.callback_query(F.data == "bk_back")
async def back_to_calendar(callback: CallbackQuery):
    today = date.today()
    await callback.message.edit_text(
        "📅 Выбери удобную дату:\n_(доступны ближайшие 60 дней, Пн–Сб)_",
        parse_mode="Markdown",
        reply_markup=_calendar_kb(today.year, today.month)
    )
    await callback.answer()


# ── Date selected ─────────────────────────────────────────────────────────────

@booking_router.callback_query(F.data.startswith("bk_d_"))
async def pick_date(callback: CallbackQuery, state: FSMContext):
    ds = callback.data[5:]  # e.g. "20260708"
    year, month, day = int(ds[:4]), int(ds[4:6]), int(ds[6:])
    d = date(year, month, day)
    day_name = DAY_NAMES[d.weekday()]
    date_pretty = f"{day} {MONTH_GEN[month]}, {day_name}"

    await state.update_data(booking_date_str=ds, booking_date_pretty=date_pretty)

    await callback.message.edit_text(
        f"📅 *{day} {MONTH_NOM[month]}* — выбери удобное время:",
        parse_mode="Markdown",
        reply_markup=_time_kb(ds)
    )
    await callback.answer()


# ── Time selected ─────────────────────────────────────────────────────────────

@booking_router.callback_query(F.data.startswith("bk_t_"))
async def pick_time(callback: CallbackQuery, state: FSMContext):
    # format: bk_t_20260708_14:00
    payload = callback.data[5:]            # "20260708_14:00"
    date_str, time_str = payload.split("_", 1)

    user_data = await state.get_data()
    date_pretty = user_data.get("booking_date_pretty", date_str)

    await state.update_data(booking_date_str=date_str, booking_time_str=time_str)
    await state.set_state(BookingState.waiting_concern)

    await callback.message.edit_text(
        f"📅 {date_pretty.capitalize()} в {time_str} — отлично!\n\n"
        f"Напиши в двух словах, что тебя беспокоит — "
        f"это поможет Еве подготовиться к встрече 🤍\n\n"
        f"_Можешь написать совсем кратко, например: «тревога на работе» или «отношения»_",
        parse_mode="Markdown"
    )
    await callback.answer()


@booking_router.message(BookingState.waiting_concern)
async def receive_concern(message: Message, state: FSMContext):
    concern = message.text.strip()
    user_data = await state.get_data()
    date_str   = user_data.get("booking_date_str", "")
    time_str   = user_data.get("booking_time_str", "")
    date_pretty = user_data.get("booking_date_pretty", date_str)
    await state.clear()

    user_id    = message.from_user.id
    first_name = message.from_user.first_name or ""
    username   = f"@{message.from_user.username}" if message.from_user.username else "без username"

    anxiety_type = get_user_type(user_id)
    type_label   = TYPE_NAMES.get(anxiety_type, "не определён") if anxiety_type else "не определён"

    save_booking(user_id, f"{date_pretty} в {time_str}", date_str, time_str)

    # Message to user
    await message.answer(
        f"⏳ Запрос отправлен!\n\n"
        f"📅 {date_pretty.capitalize()} в {time_str}\n\n"
        f"Ева подтвердит запись в ближайшее время — и я тебе напишу 🤍"
    )

    # Notification to Eva
    admin_kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"bk_ok_{user_id}_{date_str}_{time_str}"),
        InlineKeyboardButton(text="❌ Отклонить",   callback_data=f"bk_no_{user_id}"),
    ]])

    await message.bot.send_message(
        ADMIN_ID,
        f"📅 *Новая запись!*\n\n"
        f"👤 {first_name} {username}\n"
        f"ID: `{user_id}`\n"
        f"Тип тревоги: {type_label}\n"
        f"🕐 {date_pretty.capitalize()} в {time_str}\n\n"
        f"💬 Запрос: _{concern}_",
        parse_mode="Markdown",
        reply_markup=admin_kb
    )


# ── Admin: confirm ────────────────────────────────────────────────────────────

@booking_router.callback_query(F.data.startswith("bk_ok_"))
async def admin_confirm(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer()
        return
    # bk_ok_{user_id}_{date_str}_{time_str}
    parts = callback.data[6:].split("_")
    user_id  = int(parts[0])
    date_str = parts[1]
    time_str = parts[2]

    year, month, day = int(date_str[:4]), int(date_str[4:6]), int(date_str[6:])
    date_display = f"{day} {MONTH_GEN[month]}"

    # Другая заявка на этот же день/время уже подтверждена — не даём
    # случайно продать один и тот же слот дважды.
    if is_slot_booked(date_str, time_str):
        await callback.answer(
            "⚠️ Это время уже подтверждено другому клиенту — отклони эту заявку или выбери другой слот",
            show_alert=True
        )
        return

    try:
        # create_payment_amount — синхронный запрос к ЮKassa; уводим в executor,
        # чтобы не блокировать event loop бота на время сетевого запроса.
        loop = asyncio.get_running_loop()
        payment_url = await loop.run_in_executor(
            None, create_payment_amount, user_id, SESSION_PRICE, "Сессия с психологом", "session"
        )
    except Exception as e:
        logger.error("Booking payment link creation failed: %s", e)
        await callback.answer("Не удалось создать ссылку на оплату, попробуй ещё раз через минуту", show_alert=True)
        return

    pay_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"💳 Оплатить {SESSION_PRICE}₽", url=payment_url)],
        [InlineKeyboardButton(text="📄 Условия оферты", url="https://levinaeva.com/oferta.html")],
    ])

    try:
        await callback.bot.send_message(
            user_id,
            f"✅ Запись подтверждена!\n\n"
            f"📅 {date_display} в {time_str}\n\n"
            f"Осталось оплатить сессию — {SESSION_PRICE}₽.\n"
            f"После оплаты жду тебя 🤍",
            reply_markup=pay_kb
        )
    except Exception as e:
        logger.warning("Failed to notify client about booking confirmation: %s", e)
        await callback.answer("Клиенту не удалось отправить подтверждение (мог заблокировать бота)", show_alert=True)
        return

    mark_booking_confirmed(user_id, date_str, time_str)

    try:
        await callback.message.edit_text(callback.message.text + "\n\n✅ Подтверждено")
    except Exception as e:
        logger.warning("Failed to edit admin confirmation message: %s", e)

    await callback.answer("Подтверждение отправлено")


# ── Admin: reject ─────────────────────────────────────────────────────────────

@booking_router.callback_query(F.data.startswith("bk_no_"))
async def admin_reject(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer()
        return
    user_id = int(callback.data[6:])
    today = date.today()

    await callback.bot.send_message(
        user_id,
        f"😔 К сожалению, это время уже занято.\n\n"
        f"Выбери другое — Ева будет рада найти удобный вариант 🤍",
        reply_markup=_calendar_kb(today.year, today.month)
    )

    await callback.message.edit_text(callback.message.text + "\n\n❌ Отклонено")
    await callback.answer("Отказ отправлен")
