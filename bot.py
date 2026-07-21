import asyncio
import logging
import os
import traceback

from aiogram import Bot, Dispatcher
from aiogram.types import ErrorEvent, BotCommand

from config import BOT_TOKEN, ADMIN_ID
from telegram_session import RetryingAiohttpSession
from fsm_storage import SQLiteStorage

from handlers.start import router as start_router
from handlers.consent import router as consent_router
from handlers.quiz import router as quiz_router
from handlers.result import router as result_router
from handlers.admin import router as admin_router
from handlers.ai_helper import router as ai_helper_router
from handlers.booking import booking_router
from handlers.diary import diary_router
from handlers.thought_record import thought_router
from handlers.referral import referral_router
from handlers.reviews import reviews_router
from handlers.fallback import router as fallback_router

from database import init_db
from funnel_worker import start_funnel_worker
from web_server import start_web_server

# Логи: в файл + в консоль
_log_dir = os.path.dirname(os.path.abspath(__file__))
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(_log_dir, "bot.log"), encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN, session=RetryingAiohttpSession(timeout=60))

dp = Dispatcher(storage=SQLiteStorage())

# Подключаем роутеры
dp.include_router(start_router)
dp.include_router(consent_router)
dp.include_router(quiz_router)
dp.include_router(result_router)
dp.include_router(admin_router)
dp.include_router(ai_helper_router)
dp.include_router(booking_router)
dp.include_router(diary_router)
dp.include_router(thought_router)
dp.include_router(referral_router)
dp.include_router(reviews_router)
dp.include_router(fallback_router)


@dp.errors()
async def global_error_handler(event: ErrorEvent):
    logger.error(f"Unhandled error: {event.exception}", exc_info=event.exception)
    try:
        tb = "".join(traceback.format_exception(type(event.exception), event.exception, event.exception.__traceback__))
        short = tb[-800:] if len(tb) > 800 else tb
        await bot.send_message(
            ADMIN_ID,
            f"🚨 Необработанная ошибка\n\n<code>{short}</code>",
            parse_mode="HTML"
        )
    except Exception:
        pass


async def main():
    init_db()

    try:
        await bot.set_my_commands([
            BotCommand(command="start", description="Начать / Главная"),
            BotCommand(command="mytype", description="Мой тип тревоги"),
            BotCommand(command="restart", description="Пройти тест заново"),
            BotCommand(command="help", description="Помощь"),
        ])
    except Exception:
        # Не критично для работы бота — не блокируем старт из-за этого
        logger.error("Failed to set bot commands", exc_info=True)

    # Запускаем в фоне, чтобы не блокировать polling
    asyncio.create_task(
        start_funnel_worker(bot)
    )

    asyncio.create_task(
        start_web_server(bot)
    )

    logger.info("Bot started OK")

    # Разовый сетевой сбой (например, при bot.me() перед началом polling)
    # не должен убивать весь процесс — просто пробуем снова, без падения
    # в systemd-рестарт (это медленнее и сбрасывает состояние диалогов).
    while True:
        try:
            await dp.start_polling(bot)
            break
        except Exception:
            logger.error("Polling crashed, retrying in 5s", exc_info=True)
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())