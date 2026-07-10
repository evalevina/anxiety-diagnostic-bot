import logging

from aiogram import Router
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from keyboards import MAIN_MENU

router = Router()
logger = logging.getLogger(__name__)


@router.message()
async def fallback_message(message: Message, state: FSMContext):
    # Срабатывает, только если ни один другой роутер не обработал сообщение —
    # например, если FSM-состояние пользователя потерялось после рестарта бота
    # (MemoryStorage не переживает перезапуск процесса).
    await state.clear()
    try:
        await message.answer(
            "Кажется, я потерял нить разговора 🤍\n\n"
            "Нажми /start или выбери пункт в меню ниже.",
            reply_markup=MAIN_MENU
        )
    except Exception as e:
        logger.warning("Failed to send fallback message: %s", e)
