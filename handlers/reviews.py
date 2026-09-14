from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from states.quiz_states import ReviewState
from database import save_review

reviews_router = Router()


@reviews_router.callback_query(F.data == "leave_review")
async def ask_for_review(callback: CallbackQuery, state: FSMContext):

    await state.set_state(ReviewState.waiting_text)

    await callback.answer()
    await callback.message.answer(
        "Буду очень рада твоему отзыву 🤍\n\n"
        "Напиши несколько слов — как тебе разбор, что изменилось, "
        "что было самым полезным?"
    )


@reviews_router.message(ReviewState.waiting_text)
async def process_review(message: Message, state: FSMContext):

    if not message.text:
        await message.answer("Напиши отзыв текстом 🤍")
        return

    text = message.text.strip()
    user_id = message.from_user.id

    save_review(user_id, text)

    await state.clear()

    await message.answer(
        "Спасибо большое! Твой отзыв очень важен для меня 🌸\n\n"
        "Это помогает мне становиться лучше — и помогает другим девушкам "
        "решиться на путь к спокойствию."
    )


@reviews_router.callback_query(F.data == "skip_review")
async def skip_review(callback: CallbackQuery):

    await callback.answer()
    await callback.message.answer(
        "Хорошо, не буду настаивать 🤍\n"
        "Если захочешь поделиться позже — я здесь."
    )
