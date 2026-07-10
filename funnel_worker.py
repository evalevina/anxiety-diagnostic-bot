import asyncio
import logging
import os
import time
from urllib.parse import quote

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.exceptions import TelegramForbiddenError, TelegramNetworkError

logger = logging.getLogger(__name__)

from database import (
    get_pending_tasks,
    mark_task_sent,
    get_user_type,
    get_user_bought,
    get_diary_history,
    get_last_diary_time,
    add_funnel_task,
    is_unsubscribed
)

from yookassa_payment import create_payment
from tips import TIPS
from config import GROUP_PROGRAM_LINK, GROUP_PROGRAM_PRICE, ADMIN_ID, BOT_USERNAME

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


TYPE_NAMES = {
    "A": "🔍 СКАНЕР",
    "B": "🌪 КАТАСТРОФИСТ",
    "C": "🌫 ЗАМИРАТЕЛЬ",
    "D": "🎯 КОНТРОЛЁР",
}

CASE_STUDIES = {
    "A": (
        "«Ко мне пришла Лена. Не могла работать из дома — всё время прислушивалась, "
        "считывала, что чувствуют близкие в соседней комнате. "
        "Через месяц по программе — впервые смогла закрыть дверь и работать 4 часа в потоке»."
    ),
    "B": (
        "«Маша не спала по ночам — гуглила симптомы и хоронила себя. "
        "Через 3 недели — спит 8 часов, забыла, когда последний раз открывала медицинский сайт»."
    ),
    "C": (
        "«Оля не могла сказать «нет» начальнику. Замирала и брала ещё работу. "
        "Через месяц — впервые отказалась от переработки. Через 3 — выторговала повышение»."
    ),
    "D": (
        "«Аня не спала нормально 2 года, контролировала всё. "
        "Через месяц — впервые проспала 8 часов. "
        "Через 3 — ушла с работы, которая её убивала, в свой проект»."
    ),
}


async def funnel_worker(bot):

    while True:

        tasks = get_pending_tasks()

        for task_id, user_id, message_type in tasks:

            try:

                # Пропускаем отписавшихся (кроме системных задач)
                if message_type not in ("quiz_reminder",) and is_unsubscribed(user_id):
                    mark_task_sent(task_id)
                    continue

                if message_type == "quiz_reminder":

                    # Отправляем только тем, кто не прошёл тест
                    anxiety_type = get_user_type(user_id)
                    if not anxiety_type:
                        await bot.send_message(
                            user_id,
                            "Ты начала разбор, но куда-то пропала 🤍\n\n"
                            "Всего 5 вопросов — и узнаешь свой тип тревоги.\n"
                            "Обычно это занимает 4 минуты.\n\n"
                            "Нажми /start чтобы продолжить 👇"
                        )

                elif message_type == "1h":

                    await bot.send_message(
                        user_id,
                        "🤍 Пока ты думаешь...\n\n"
                        "Есть одна вещь, которую почти никто не замечает.\n\n"
                        "Тревога редко начинается во взрослом возрасте.\n\n"
                        "Чаще всего её корни уходят намного глубже."
                    )

                elif message_type == "24h":

                    anxiety_type = get_user_type(user_id)

                    type_name = TYPE_NAMES.get(anxiety_type, "тревоги")
                    case_study = CASE_STUDIES.get(
                        anxiety_type,
                        "«Работа с типом тревоги даёт результат уже через месяц.»"
                    )

                    loop = asyncio.get_running_loop()
                    payment_url = await loop.run_in_executor(None, create_payment, user_id)

                    keyboard = InlineKeyboardMarkup(
                        inline_keyboard=[
                            [
                                InlineKeyboardButton(
                                    text="💳 Забрать за 1490₽",
                                    url=payment_url
                                )
                            ]
                        ]
                    )

                    await bot.send_message(
                        user_id,

                        f"Привет 🤍\n\n"
                        f"Вчера ты прошла разбор и узнала, что ты — {type_name}.\n\n"
                        f"Хочу поделиться кейсом:\n\n"
                        f"{case_study}\n\n"
                        f"Это не магия. Это система, которая внутри «Полного разбора» 👇",

                        reply_markup=keyboard
                    )

                elif message_type == "72h":

                    loop = asyncio.get_running_loop()
                    payment_url_72h = await loop.run_in_executor(None, create_payment, user_id)

                    keyboard = InlineKeyboardMarkup(
                        inline_keyboard=[
                            [
                                InlineKeyboardButton(
                                    text="💳 Успеть за 1490₽",
                                    url=payment_url_72h
                                )
                            ],
                            [
                                InlineKeyboardButton(
                                    text="❌ Не интересно",
                                    callback_data="unsubscribe"
                                )
                            ]
                        ]
                    )

                    await bot.send_message(
                        user_id,

                        "Три дня — это время, за которое обычно принимают решение 🕯\n\n"
                        "Сегодня последний день специальной цены: 1490₽ вместо 3490₽.\n\n"
                        "Если что-то останавливает — это нормально. "
                        "Вложить деньги в себя бывает страшно, "
                        "особенно когда не знаешь наверняка, поможет ли.\n\n"
                        "Я делала разбор так, чтобы результат был виден с первых дней — не через полгода.\n\n"
                        "Если решишь — буду рада. Если нет — всё равно рада, что ты здесь 🤍",

                        reply_markup=keyboard
                    )

                elif message_type.startswith("tip_"):

                    anxiety_type = get_user_type(user_id)
                    if anxiety_type and anxiety_type in TIPS:
                        day_index = int(message_type.split("_")[1]) - 1
                        tip_text = TIPS[anxiety_type][day_index]
                        await bot.send_message(user_id, tip_text)

                elif message_type == "retest_30d":

                    keyboard = InlineKeyboardMarkup(
                        inline_keyboard=[
                            [InlineKeyboardButton(text="🔁 Пройти повторно", callback_data="retest")]
                        ]
                    )

                    await bot.send_message(
                        user_id,
                        "Прошёл месяц с момента твоего разбора 🤍\n\n"
                        "Тревога — штука живая. Она может меняться.\n"
                        "Хочешь проверить — изменился ли твой тип?",
                        reply_markup=keyboard
                    )

                elif message_type == "review_3d":

                    keyboard = InlineKeyboardMarkup(
                        inline_keyboard=[
                            [InlineKeyboardButton(text="✍️ Написать отзыв", callback_data="leave_review")],
                            [InlineKeyboardButton(text="Пропустить", callback_data="skip_review")]
                        ]
                    )

                    await bot.send_message(
                        user_id,
                        "Прошло несколько дней с момента покупки разбора 🤍\n\n"
                        "Буду рада узнать — что тебе дал разбор?\n"
                        "Если захочешь поделиться — я здесь.",
                        reply_markup=keyboard
                    )

                elif message_type == "upsell2_7d":

                    if GROUP_PROGRAM_LINK and GROUP_PROGRAM_LINK != "https://example.com":
                        keyboard = InlineKeyboardMarkup(
                            inline_keyboard=[
                                [InlineKeyboardButton(text=f"💎 Узнать подробнее", url=GROUP_PROGRAM_LINK)],
                                [InlineKeyboardButton(text="Не сейчас", callback_data="no_session")]
                            ]
                        )

                        await bot.send_message(
                            user_id,
                            f"Ты уже знаешь свой тип тревоги.\n\n"
                            f"Следующий шаг — небольшая групповая программа со мной.\n\n"
                            f"Работаем глубоко, вместе, в маленьком кругу — максимум 7 человек.\n"
                            f"10 встреч в Zoom, по 60 минут каждая.\n"
                            f"Стоимость — {GROUP_PROGRAM_PRICE}₽ за встречу.\n\n"
                            f"Для тех кто уже купил разбор — приоритетное место 🤍",
                            reply_markup=keyboard
                        )

                elif message_type == "show_offer":

                    if not get_user_bought(user_id):
                        loop = asyncio.get_running_loop()
                        payment_url = await loop.run_in_executor(None, create_payment, user_id)

                        share_link = f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"
                        share_url = (
                            f"https://t.me/share/url?url={quote(share_link)}"
                            f"&text={quote('Узнай свой тип тревоги за 5 минут — бесплатно 🤍')}"
                        )

                        offer_keyboard = InlineKeyboardMarkup(
                            inline_keyboard=[
                                [InlineKeyboardButton(text="💳 Купить за 1490₽", url=payment_url)],
                                [InlineKeyboardButton(text="✅ Я оплатил(а)", callback_data="paid")],
                                [InlineKeyboardButton(text="🤔 Подумать", callback_data="think")],
                                [InlineKeyboardButton(text="📄 Условия оферты", url="https://levinaeva.com/oferta.html")],
                            ]
                        )

                        offer_text = (
                            "📕 «Полный разбор твоего типа тревоги»\n\n"
                            "Что внутри (PDF + 3 аудио):\n\n"
                            "✅ Глубокий разбор твоего типа на 25 страниц\n"
                            "✅ Как тип влияет на отношения, работу, тело\n"
                            "✅ Пошаговый план + упражнения и дневник\n"
                            "✅ 3 аудио-медитации под твой тип (15–20 мин каждая)\n"
                            "✅ Чек-лист «Когда пора к психологу»\n\n"
                            "🎁 Бонус: запись разбора-вебинара\n"
                            "«Как тревога съедает деньги и отношения» (обычно 990₽)\n\n"
                            "━━━━━━━━━━━━\n"
                            "💰 Обычная цена: 3 490 ₽\n"
                            "🔥 Сейчас: 1 490 ₽\n"
                            "⏰ Цена действует 72 часа после прохождения бота\n"
                            "━━━━━━━━━━━━"
                        )

                        await bot.send_message(
                            user_id,
                            "Заметила, как точно попало? 🎯\n\n"
                            "То, что ты сейчас прочитала — это верхушка.\n\n"
                            "У каждого типа есть глубокие корни:\n"
                            "откуда пришёл,\n"
                            "как влияет на отношения,\n"
                            "деньги,\n"
                            "тело,\n"
                            "сон.\n\n"
                            "Если хочешь разобраться до конца —\n"
                            "у меня есть кое-что 👇"
                        )

                        image_path = os.path.join(BASE_DIR, "images", "offer.png")
                        await bot.send_photo(
                            user_id,
                            FSInputFile(image_path),
                            caption=offer_text,
                            reply_markup=offer_keyboard
                        )

                elif message_type == "diary_reminder":

                    last_time = get_last_diary_time(user_id)

                    if last_time is None:
                        # Никогда не пользовался дневником — не беспокоим
                        pass
                    elif time.time() - last_time > 3 * 86400:
                        # Был активен в дневнике, но давно не заходил
                        await bot.send_message(
                            user_id,
                            "📔 Давно не заглядывала в дневник тревоги...\n\n"
                            "Регулярные записи помогают замечать паттерны "
                            "и видеть прогресс.\n\n"
                            "Займёт 1 минуту — нажми «📔 Дневник» в меню 🤍"
                        )
                        add_funnel_task(user_id, 3 * 86400, "diary_reminder")
                    else:
                        # Недавно делал запись — просто переносим напоминание
                        add_funnel_task(user_id, 3 * 86400, "diary_reminder")

                elif message_type == "onboarding_day1":

                    anxiety_type = get_user_type(user_id)

                    first_steps = {
                        "A": (
                            "Попробуй упражнение «Выключи радар» три раза — "
                            "утром, в обед и вечером. По 3 минуты каждый раз.\n\n"
                            "Это упражнение есть на первых страницах разбора."
                        ),
                        "B": (
                            "Поймай одну катастрофическую мысль сегодня и разбери её: "
                            "«А что если будет хорошо? Нейтрально? Средне?»\n\n"
                            "Техника «А что если хорошо?» — в твоём разборе."
                        ),
                        "C": (
                            "При любом напряжении сегодня — назови вслух 5 вещей, "
                            "которые видишь. Сразу, не откладывая.\n\n"
                            "Заземление 5-4-3-2-1 — твой главный инструмент, он в разборе."
                        ),
                        "D": (
                            "Возьми лист и выпиши всё, что тебя тревожит прямо сейчас. "
                            "Раздели на два столбца: «могу влиять» / «не могу».\n\n"
                            "Упражнение «Зона невлияния» — в разборе на первых страницах."
                        ),
                    }

                    tip = first_steps.get(
                        anxiety_type,
                        "Начни с любого упражнения из разбора — даже 5 минут уже меняют состояние."
                    )

                    await bot.send_message(
                        user_id,
                        f"Привет 🤍\n\n"
                        f"Ты уже получила «Полный разбор» — это большой шаг.\n\n"
                        f"Рекомендация на первый день:\n{tip}\n\n"
                        f"Не нужно делать всё сразу. Один маленький шаг — уже прогресс 🌱\n\n"
                        f"Если что-то непонятно — я рядом в «AI-помощнике» или напрямую 🤍"
                    )

                elif message_type == "diary_weekly":

                    history = get_diary_history(user_id, days=7)

                    if not history:
                        await bot.send_message(
                            user_id,
                            "📔 Ты давно не заглядывала в дневник тревоги.\n\n"
                            "Даже одна запись в неделю помогает отследить динамику 🌱\n\n"
                            "Нажми «📔 Дневник» в меню — займёт 1 минуту 🤍"
                        )
                    else:
                        avg = sum(s for s, _, _ in history) / len(history)
                        max_score = max(s for s, _, _ in history)
                        min_score = min(s for s, _, _ in history)

                        if avg <= 4:
                            mood = "Отлично — тревога под контролем 🌿"
                        elif avg <= 6:
                            mood = "Средний уровень — продолжай работу 🌀"
                        else:
                            mood = "Тревога держится высоко. Береги себя 💛"

                        await bot.send_message(
                            user_id,
                            f"📊 Итоги твоей недели в дневнике:\n\n"
                            f"Записей за неделю: {len(history)}\n"
                            f"Средний уровень тревоги: {avg:.1f}/10\n"
                            f"Самый спокойный день: {min_score}/10\n"
                            f"Самый тревожный день: {max_score}/10\n\n"
                            f"{mood}\n\n"
                            f"Продолжай вести дневник — это уже работа с тревогой 🤍"
                        )

                    # Планируем следующий еженедельный итог
                    add_funnel_task(user_id, 7 * 86400, "diary_weekly")

                mark_task_sent(task_id)

            except TelegramForbiddenError:
                mark_task_sent(task_id)
                logger.info(f"Воронка: user {user_id} заблокировал бота, задача {task_id} закрыта")

            except TelegramNetworkError as e:
                logger.warning(f"Воронка: сетевой таймаут task={task_id} user={user_id}, повтор через 60с")

            except Exception as e:
                logger.error(f"Ошибка воронки task={task_id} user={user_id}: {e}")
                try:
                    await bot.send_message(
                        ADMIN_ID,
                        f"⚠️ Ошибка воронки\n\n"
                        f"Task: {task_id} | Type: {message_type}\n"
                        f"User: {user_id}\n"
                        f"Error: {e}"
                    )
                except Exception:
                    pass

        await asyncio.sleep(60)


async def start_funnel_worker(bot):
    await funnel_worker(bot)
