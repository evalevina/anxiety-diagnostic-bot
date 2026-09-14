from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_referral_count
from config import BOT_USERNAME

referral_router = Router()


@referral_router.message(F.text == "🎁 Пригласить подругу")
async def cmd_referral(message: Message, state: FSMContext):
    await state.clear()

    user_id = message.from_user.id
    count = get_referral_count(user_id)

    ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📤 Поделиться ссылкой", switch_inline_query=ref_link)]
        ]
    )

    friends_text = ""
    if count == 0:
        friends_text = "Пока ни одной подруги не пришло по твоей ссылке."
    elif count == 1:
        friends_text = "По твоей ссылке пришла *1 подруга* 🎉"
    elif count < 5:
        friends_text = f"По твоей ссылке пришли *{count} подруги* 🎉"
    else:
        friends_text = f"По твоей ссылке пришли *{count} подруг* 🎉 Ты звезда!"

    await message.answer(
        f"🎁 Пригласи подругу — помоги ей понять свою тревогу!\n\n"
        f"Твоя личная ссылка:\n"
        f"`{ref_link}`\n\n"
        f"{friends_text}\n\n"
        f"Просто скопируй ссылку и отправь подруге 💌",
        parse_mode="Markdown",
        reply_markup=keyboard
    )
