import asyncio
import logging
import os

logger = logging.getLogger(__name__)

from aiogram import Router, F
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    ReplyKeyboardMarkup,
    KeyboardButton,
    FSInputFile
)
from aiogram.fsm.context import FSMContext

from database import (
    update_result,
    save_quiz_result,
    set_thinking,
    set_bought,
    set_saw_offer,
    add_funnel_task,
    save_message,
    get_user_bought,
    get_latest_payment_id,
    has_pending_funnel_tasks,
    has_tip_tasks,
    get_user_type,
    get_referrer_id,
    has_diary_reminder_task,
    has_diary_weekly_task
)

from yookassa_payment import check_payment_status
from materials import send_materials
from keyboards import MAIN_MENU
from states.quiz_states import QuizState
from results_data import RESULTS

router = Router()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

QUESTION_LINK = "https://t.me/evalevina_psy"

TYPE_NAMES = {
    "A": "Сканера",
    "B": "Катастрофиста",
    "C": "Замирателя",
    "D": "Контролёра",
}

# ---------------- SHOW RESULT ----------------

async def show_result(message, state: FSMContext):

    user_data = await state.get_data()

    result = user_data.get("result")
    result_secondary = user_data.get("result_secondary")

    if not result:

        await message.answer(
            "Произошла ошибка определения результата.\n\n"
            "Пожалуйста, пройди тест заново через /start"
        )

        return

    # Проверяем до обновления — первое ли завершение теста
    is_first_completion = get_user_type(message.chat.id) is None

    update_result(
        message.chat.id,
        result
    )
    save_quiz_result(message.chat.id, result)

    # Благодарность рефереру при первом прохождении
    # Без имени приглашённой(ого) — это её персональные данные, раскрывать
    # рефереру без отдельного согласия нельзя.
    if is_first_completion:
        referrer_id = get_referrer_id(message.chat.id)
        if referrer_id:
            try:
                await message.bot.send_message(
                    referrer_id,
                    "🤍 Кто-то прошёл разбор по твоей ссылке!\n\n"
                    "Спасибо что делишься — это важно 🌿"
                )
            except Exception:
                pass

    # Добавляем задачи ежедневных советов если ещё нет
    if not has_tip_tasks(message.chat.id):
        for day in range(1, 8):
            add_funnel_task(message.chat.id, day * 86400, f"tip_{day}")
        add_funnel_task(message.chat.id, 30 * 86400, "retest_30d")

    # Напоминание о дневнике через 3 дня
    if not has_diary_reminder_task(message.chat.id):
        add_funnel_task(message.chat.id, 3 * 86400, "diary_reminder")

    # Еженедельный итог дневника через 7 дней
    if not has_diary_weekly_task(message.chat.id):
        add_funnel_task(message.chat.id, 7 * 86400, "diary_weekly")

    result_data = RESULTS[result]

    save_message(message.chat.id, "bot", result_data["name"])

    await message.answer(
        "🧠 Анализирую ответы..."
    )

    await asyncio.sleep(4)

    image_path = os.path.join(BASE_DIR, "images", result_data["image"])

    await message.answer_photo(
        photo=FSInputFile(image_path),
        caption=f"{result_data['name']}\n\n{result_data['text']}"
    )

    await asyncio.sleep(4)

    secondary_note = ""
    if result_secondary:
        secondary_name = TYPE_NAMES[result_secondary]
        secondary_note = (
            f"💡 Это твой доминирующий тип — тот, что проявляется сильнее всего под давлением. "
            f"Также заметны черты {secondary_name}. Чистые типы встречаются редко — смешанный профиль это норма 🤍\n\n"
        )

    await message.answer(secondary_note + result_data["exercise"])

    # ---------------- ПРОДАЖА ----------------

    set_saw_offer(message.chat.id)
    add_funnel_task(message.chat.id, 30, "show_offer")

    await message.answer("🤍", reply_markup=MAIN_MENU)


# ---------------- THINK ----------------

@router.callback_query(F.data == "think")
async def think(callback: CallbackQuery):

    save_message(callback.from_user.id, "user", "🤔 Подумать (отложил покупку)")

    set_thinking(
        callback.from_user.id
    )

    await callback.message.answer(
        "🤍 Хорошо.\n\n"

        "Я не буду давить.\n\n"

        "Но позже пришлю тебе ещё один разбор,\n"
        "который может многое объяснить."
    )

    # Добавляем задачи только если воронка ещё не запущена
    if not has_pending_funnel_tasks(callback.from_user.id):
        add_funnel_task(callback.from_user.id, 3600, "1h")
        add_funnel_task(callback.from_user.id, 24 * 3600, "24h")
        add_funnel_task(callback.from_user.id, 72 * 3600, "72h")

    await callback.answer()


# ---------------- PAID ----------------

@router.callback_query(F.data == "paid")
async def paid(callback: CallbackQuery):

    user_id = callback.from_user.id

    save_message(user_id, "user", "✅ Я оплатил(а)")

    # Если webhook уже обработал оплату — просто подтверждаем
    if get_user_bought(user_id):
        await callback.message.answer("Ты уже с нами 🎉 Проверь сообщения выше — материалы уже отправлены 🤍")
        await callback.answer()
        return

    # Проверяем статус платежа в ЮКассе
    payment_id = get_latest_payment_id(user_id)

    if not payment_id:
        await callback.message.answer(
            "Не нашла твой платёж 🤔\n\n"
            "Напиши мне напрямую — разберёмся: @evalevina_psy 🤍"
        )
        await callback.answer()
        return

    try:
        status = check_payment_status(payment_id)
    except Exception as e:
        logger.error(f"Payment check error user={user_id}: {e}")
        await callback.message.answer(
            "Не смогла проверить платёж прямо сейчас 🤔\n\n"
            "Если оплатила — напиши мне: @evalevina_psy 🤍"
        )
        await callback.answer()
        return

    if status == "succeeded":

        set_bought(user_id)
        save_message(user_id, "bot", "✅ Оплата подтверждена")

        await send_materials(callback.message.bot, user_id)

        add_funnel_task(user_id, 86400, "onboarding_day1")
        add_funnel_task(user_id, 259200, "review_3d")
        add_funnel_task(user_id, 604800, "upsell2_7d")

    else:

        await callback.message.answer(
            "Платёж ещё обрабатывается 🕐\n\n"
            "Подожди пару минут и нажми «✅ Я оплатил(а)» снова.\n\n"
            "Если оплатила, но кнопка не срабатывает — напиши мне: @evalevina_psy 🤍"
        )

    await callback.answer()


# ---------------- NO SESSION ----------------

@router.callback_query(F.data == "no_session")
async def no_session(callback: CallbackQuery):

    await callback.message.answer(
        "Хорошо 🤍\n\n"
        "Если захочешь — предложение действует 7 дней."
    )

    await callback.answer()


# ---------------- RETEST ----------------

@router.callback_query(F.data == "retest")
async def retest(callback: CallbackQuery, state: FSMContext):
    from database import set_started_quiz, has_pending_quiz_reminder, add_funnel_task as _add_task, save_message as _save_msg

    await callback.answer()

    user_id = callback.from_user.id
    set_started_quiz(user_id)
    _save_msg(user_id, "user", "🔁 Повторный тест")

    await state.clear()
    await state.set_state(QuizState.waiting_phone)

    if not has_pending_quiz_reminder(user_id):
        _add_task(user_id, 2 * 3600, "quiz_reminder")

    phone_keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Поделиться номером", request_contact=True)],
            [KeyboardButton(text="Пропустить")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

    await callback.message.answer(
        "Прежде чем начать — оставь свой номер телефона.\n\n"
        "Это поможет мне связаться с тобой, "
        "если захочешь записаться на консультацию 🤍",
        reply_markup=phone_keyboard
    )
