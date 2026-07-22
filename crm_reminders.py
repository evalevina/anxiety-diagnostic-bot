import asyncio
import logging

from database import get_due_reminders, mark_reminder_notified, get_crm_client_detail
from config import ADMIN_ID

logger = logging.getLogger(__name__)

CHECK_INTERVAL = 300  # 5 минут — напоминания не так срочны, как воронка


async def crm_reminder_worker(bot):

    logger.info("CRM reminder worker started")

    while True:

        try:

            for note_id, user_id, text, reminder_at in get_due_reminders():

                detail = get_crm_client_detail(user_id)
                name = " ".join(
                    filter(None, [detail.get("first_name"), detail.get("last_name")])
                ) if detail else ""
                who = name or (f"@{detail['username']}" if detail and detail.get("username") else f"id{user_id}")

                await bot.send_message(
                    ADMIN_ID,
                    f"🔔 Напоминание по клиенту {who} (id {user_id})\n\n{text}"
                )

                mark_reminder_notified(note_id)

        except Exception:
            logger.error("CRM reminder worker error", exc_info=True)

        await asyncio.sleep(CHECK_INTERVAL)


async def start_crm_reminder_worker(bot):
    await crm_reminder_worker(bot)
