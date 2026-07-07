from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton
)

from states.quiz_states import ThoughtRecordState
from database import (
    get_user_bought, save_thought_record,
    get_thought_record_count, get_common_distortion
)

thought_router = Router()

DISTORTIONS = {
    "catastrophe": "🌪 Представляю худший вариант",
    "mindread": "🔮 «Знаю», что думают другие",
    "blackwhite": "⚫⚪ Всё или ничего",
    "always": "🔁 «Всегда» или «никогда»",
    "shoulds": "📏 «Я должна была»",
    "personalize": "🎯 Это точно из-за меня",
    "unsure": "🤷 Не уверена",
}


def _distortion_keyboard():
    codes = list(DISTORTIONS.items())
    rows = []
    for i in range(0, len(codes) - 1, 2):
        row = [InlineKeyboardButton(text=codes[i][1], callback_data=f"cbt_distortion:{codes[i][0]}")]
        if i + 1 < len(codes) - 1:
            row.append(InlineKeyboardButton(text=codes[i + 1][1], callback_data=f"cbt_distortion:{codes[i + 1][0]}"))
        rows.append(row)
    rows.append([InlineKeyboardButton(text=DISTORTIONS["unsure"], callback_data="cbt_distortion:unsure")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _rerate_keyboard():
    row1 = [InlineKeyboardButton(text=str(i), callback_data=f"cbt_rerate:{i}") for i in range(1, 6)]
    row2 = [InlineKeyboardButton(text=str(i), callback_data=f"cbt_rerate:{i}") for i in range(6, 11)]
    return InlineKeyboardMarkup(inline_keyboard=[row1, row2])


def diary_cbt_button(diary_id: int, score: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🧠 Разобрать эту мысль", callback_data=f"cbt_start:{diary_id}:{score}")
    ]])


@thought_router.callback_query(F.data.startswith("cbt_start:"))
async def cbt_start(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    await callback.answer()

    if not get_user_bought(user_id):
        return

    _, diary_id, score = callback.data.split(":")
    await state.update_data(diary_id=int(diary_id), score_before=int(score))
    await state.set_state(ThoughtRecordState.waiting_thought)

    await callback.message.answer(
        "Какая мысль пронеслась в голове в этот момент? 🤍\n\n"
        "Напиши её так, как она прозвучала внутри — своими словами."
    )


@thought_router.message(ThoughtRecordState.waiting_thought)
async def cbt_thought(message: Message, state: FSMContext):
    await state.update_data(automatic_thought=message.text.strip())
    await state.set_state(ThoughtRecordState.waiting_distortion)

    await message.answer(
        "Спасибо, что назвала её вслух — это уже часть работы.\n\n"
        "На что это похоже больше всего?",
        reply_markup=_distortion_keyboard()
    )


@thought_router.callback_query(F.data.startswith("cbt_distortion:"), ThoughtRecordState.waiting_distortion)
async def cbt_distortion(callback: CallbackQuery, state: FSMContext):
    code = callback.data.split(":", 1)[1]
    await callback.answer()
    await state.update_data(distortion=DISTORTIONS.get(code, code))
    await state.set_state(ThoughtRecordState.waiting_reframe)

    await callback.message.answer(
        "Прежде чем ответить, попробуй мысленно спросить себя:\n\n"
        "— Какие есть факты за и против этой мысли?\n"
        "— Что бы ты сказала подруге с такой же мыслью?\n"
        "— Есть ли более сбалансированный взгляд на ситуацию?\n\n"
        "Напиши, как можно посмотреть на это иначе:"
    )


@thought_router.message(ThoughtRecordState.waiting_reframe)
async def cbt_reframe(message: Message, state: FSMContext):
    await state.update_data(reframe=message.text.strip())
    await state.set_state(ThoughtRecordState.waiting_rerate)

    await message.answer(
        "Хорошо. Теперь оцени тревогу сейчас, после этого разбора — от 1 до 10:",
        reply_markup=_rerate_keyboard()
    )


@thought_router.callback_query(F.data.startswith("cbt_rerate:"), ThoughtRecordState.waiting_rerate)
async def cbt_rerate(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    score_after = int(callback.data.split(":")[1])
    await callback.answer()

    data = await state.get_data()
    score_before = data.get("score_before", 0)

    save_thought_record(
        user_id,
        data.get("diary_id"),
        data.get("automatic_thought"),
        data.get("distortion"),
        data.get("reframe"),
        score_before,
        score_after
    )
    await state.clear()

    if score_after < score_before:
        reply = f"Тревога снизилась с {score_before} до {score_after} — и это сделала ты сама 🤍"
    elif score_after == score_before:
        reply = (
            "Уровень тревоги не изменился — и это тоже нормально, реframe не всегда работает мгновенно. "
            "Ты всё равно на шаг ближе к тому, чтобы замечать свои мысли."
        )
    else:
        reply = "Сейчас может быть даже тяжелее — называть трудную мысль вслух непросто. Ты справилась с непростым шагом 🤍"

    count = get_thought_record_count(user_id)
    if count >= 3:
        common = get_common_distortion(user_id)
        if common and common[1] >= 3:
            reply += (
                f"\n\nКстати, ты уже {common[1]} раз(а) замечаешь у себя «{common[0]}» — "
                "это ценное наблюдение, с ним можно предметно поработать на консультации 📅"
            )

    await callback.message.answer(reply)
