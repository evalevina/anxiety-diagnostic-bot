from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import save_health_consent, has_health_consent

router = Router()

PRIVACY_URL = "https://levinaeva.com/privacy.html"

CONSENT_TEXT = (
    "Прежде чем продолжить 🤍\n\n"
    "Тест на тип тревоги, записи в дневнике и переписка с AI-компаньоном могут "
    "содержать сведения о состоянии здоровья — по закону это особая категория "
    "персональных данных (ст. 10 152-ФЗ), и мне нужно твоё отдельное согласие "
    "на их обработку.\n\n"
    "Полный текст — по кнопке ниже. Данные использую только для работы бота "
    "и не передаю третьим лицам."
)

DECLINE_TEXT = (
    "Хорошо, тогда пока не смогу показать тест, дневник и AI-компаньона — "
    "это как раз те функции, которые связаны с данными о состоянии.\n\n"
    "Если передумаешь — просто нажми на нужную кнопку ещё раз 🤍"
)


def consent_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📄 Политика обработки данных", url=PRIVACY_URL)],
        [InlineKeyboardButton(text="✅ Согласен(а)", callback_data="consent_accept")],
        [InlineKeyboardButton(text="❌ Не согласен(а)", callback_data="consent_decline")],
    ])


async def ensure_consent(answerable, user_id: int) -> bool:
    # Возвращает True, если согласие уже дано. Иначе показывает экран
    # согласия и возвращает False — вызывающий хендлер должен прервать
    # свой сценарий (тест / дневник / AI-компаньон).
    if has_health_consent(user_id):
        return True
    await answerable.answer(CONSENT_TEXT, reply_markup=consent_keyboard())
    return False


@router.callback_query(F.data == "consent_accept")
async def consent_accept(callback: CallbackQuery):
    save_health_consent(callback.from_user.id)
    await callback.answer("Спасибо!")
    await callback.message.answer(
        "Согласие сохранено 🤍\n\nТеперь нажми ту же кнопку ещё раз, чтобы продолжить."
    )


@router.callback_query(F.data == "consent_decline")
async def consent_decline(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(DECLINE_TEXT)
