from datetime import datetime

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton
)

from states.quiz_states import DiaryState
from database import (
    save_diary_entry, get_diary_history,
    add_funnel_task, has_diary_weekly_task,
    get_diary_streak
)

diary_router = Router()


def _score_keyboard():
    row1 = [InlineKeyboardButton(text=str(i), callback_data=f"diary_score:{i}") for i in range(1, 6)]
    row2 = [InlineKeyboardButton(text=str(i), callback_data=f"diary_score:{i}") for i in range(6, 11)]
    return InlineKeyboardMarkup(inline_keyboard=[row1, row2])


def _tag_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💼 Работа", callback_data="diary_tag:работа"),
            InlineKeyboardButton(text="💔 Отношения", callback_data="diary_tag:отношения"),
        ],
        [
            InlineKeyboardButton(text="🏠 Семья", callback_data="diary_tag:семья"),
            InlineKeyboardButton(text="🏥 Здоровье", callback_data="diary_tag:здоровье"),
        ],
        [
            InlineKeyboardButton(text="🌫 Без причины", callback_data="diary_tag:без причины"),
            InlineKeyboardButton(text="✏️ Написать своё", callback_data="diary_tag:custom"),
        ],
        [
            InlineKeyboardButton(text="— Пропустить", callback_data="diary_tag:skip"),
        ],
    ])


@diary_router.message(F.text == "📔 Дневник")
async def cmd_diary(message: Message):
    await message.answer(
        "📔 Как ты сейчас?\n\n"
        "Оцени уровень тревоги — от 1 до 10:\n\n"
        "1 — спокойно и хорошо\n"
        "10 — очень тяжело",
        reply_markup=_score_keyboard()
    )


@diary_router.callback_query(F.data.startswith("diary_score:"))
async def process_diary_score(callback: CallbackQuery, state: FSMContext):
    score = int(callback.data.split(":")[1])
    await state.update_data(diary_score=score)
    await state.set_state(DiaryState.waiting_note)
    await callback.answer()
    await callback.message.answer(
        f"Уровень тревоги: *{score}/10*\n\n"
        "Что сейчас беспокоит?",
        parse_mode="Markdown",
        reply_markup=_tag_keyboard()
    )


@diary_router.callback_query(F.data.startswith("diary_tag:"), DiaryState.waiting_note)
async def process_diary_tag(callback: CallbackQuery, state: FSMContext):
    tag = callback.data.split(":", 1)[1]
    await callback.answer()

    if tag == "custom":
        await state.set_state(DiaryState.waiting_custom_note)
        await callback.message.answer("Напиши что происходит — в паре слов 🤍")
        return

    note = None if tag == "skip" else tag
    await _save_and_respond(callback.from_user.id, state, note, callback.message)


@diary_router.message(DiaryState.waiting_custom_note)
async def process_diary_custom_note(message: Message, state: FSMContext):
    note = message.text.strip() or None
    await _save_and_respond(message.from_user.id, state, note, message)


@diary_router.message(DiaryState.waiting_note)
async def process_diary_text_note(message: Message, state: FSMContext):
    note = None if message.text.strip() == "-" else message.text.strip()
    await _save_and_respond(message.from_user.id, state, note, message)


async def _save_and_respond(user_id, state, note, message):
    data = await state.get_data()
    score = data.get("diary_score", 0)

    save_diary_entry(user_id, score, note)

    if not has_diary_weekly_task(user_id):
        add_funnel_task(user_id, 7 * 86400, "diary_weekly")

    await state.clear()

    history = get_diary_history(user_id, days=7)
    streak = get_diary_streak(user_id)
    trend_text = _build_trend(history)

    # Стрик
    streak_text = ""
    if streak == 3:
        streak_text = "\n\n🔥 3 дня подряд — так держать!"
    elif streak == 7:
        streak_text = "\n\n🌱 Неделя без пропусков — это уже привычка!"
    elif streak == 14:
        streak_text = "\n\n🔥 14 дней подряд — ты молодец!"
    elif streak == 30:
        streak_text = "\n\n🏆 30 дней! Это настоящий результат 🤍"
    elif streak >= 3:
        streak_text = f"\n\n🔥 {streak} дней подряд"

    reply = f"Записала ✅\n\n{trend_text}{streak_text}"

    # Ночной триггер
    hour = datetime.now().hour
    is_night = hour >= 23 or hour < 6

    if is_night and score >= 7:
        reply += (
            "\n\n🌙 Ночью тревога ощущается острее — это нормально.\n\n"
            "Попробуй прямо сейчас: положи руку на грудь "
            "и сделай 3 медленных выдоха.\n"
            "Ты справишься 🤍"
        )
    elif score >= 7:
        scores_above_7 = [s for s, _, _ in history if s >= 7]
        if len(scores_above_7) >= 3:
            reply += (
                "\n\n💛 Несколько дней подряд тебе нелегко.\n\n"
                "Иногда нужна живая поддержка — и это нормально.\n"
                "Если захочешь поговорить — нажми «📅 Записаться» 🤍"
            )

    await message.answer(reply, parse_mode="Markdown")


def _build_trend(history):
    if not history:
        return "Это твоя первая запись 🌱"

    bars = ""
    for score, _, ts in history[-7:]:
        dt = datetime.fromtimestamp(ts).strftime("%d.%m")
        bar = "█" * score + "░" * (10 - score)
        bars += f"{dt}: {bar} {score}\n"

    avg = sum(s for s, _, _ in history) / len(history)

    return (
        f"📊 Твой дневник за последние 7 дней:\n\n"
        f"{bars}\n"
        f"Средний уровень: *{avg:.1f}*"
    )
