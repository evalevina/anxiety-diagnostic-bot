import asyncio
import logging

from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import TelegramNetworkError

logger = logging.getLogger(__name__)


class RetryingAiohttpSession(AiohttpSession):
    # Соединение с Telegram API из РФ иногда коротко "заикается"
    # (TelegramNetworkError / таймаут). Раньше это приходилось ловить
    # вручную в каждом хендлере — теперь ретраим централизованно для
    # любого запроса (send_message, send_chat_action и т.д.).
    async def make_request(self, bot, method, timeout=None):
        last_error = None
        for attempt in range(3):
            try:
                return await super().make_request(bot, method, timeout)
            except TelegramNetworkError as e:
                last_error = e
                logger.warning(
                    "Telegram API %s failed (attempt %d): %s",
                    method.__api_method__, attempt + 1, e
                )
                if attempt < 2:
                    await asyncio.sleep(1)
        raise last_error
