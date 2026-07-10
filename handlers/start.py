import os
import asyncio

from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    FSInputFile
)
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.fsm.context import FSMContext

from database import save_user, save_message, save_user_source, save_user_referral, get_user_profile, get_finished_count, set_unsubscribed
from keyboards import MAIN_MENU

router = Router()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TYPE_LABELS = {
    "A": "🔍 Сканер",
    "B": "🌪 Катастрофист",
    "C": "🌫 Замиратель",
    "D": "🎯 Контролёр",
}


# ---------------- START ----------------

@router.message(CommandStart())
async def start(message: Message, command: CommandObject, state: FSMContext):

    save_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
        message.from_user.last_name
    )

    if command.args:
        args = command.args.strip()
        if args.startswith("ref_"):
            try:
                referrer_id = int(args[4:])
                if referrer_id != message.from_user.id:
                    save_user_referral(message.from_user.id, referrer_id)
            except ValueError:
                pass
        else:
            save_user_source(message.from_user.id, args)

    save_message(message.from_user.id, "user", "/start")

    # Персональное приветствие для вернувшихся пользователей
    profile = get_user_profile(message.from_user.id)
    if profile and profile[1]:  # anxiety_type заполнен — тест пройден
        first_name, anxiety_type, bought, finished = profile
        name = first_name or "снова"
        type_label = TYPE_LABELS.get(anxiety_type, "")

        if bought:
            await message.answer(
                f"С возвращением, {name}! 🤍\n\n"
                f"Ты — {type_label}.\n\n"
                f"Как дела с тревогой? Дневник и AI-помощник всегда здесь 👇",
                reply_markup=MAIN_MENU
            )
        else:
            keyboard_return = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="💳 Купить разбор", callback_data="returning_buy")],
                    [InlineKeyboardButton(text="🔁 Пройти тест заново", callback_data="start_quiz")]
                ]
            )
            await message.answer(
                f"С возвращением, {name}! 🤍\n\n"
                f"Ты — {type_label}.\n\n"
                f"«Полный разбор» всё ещё ждёт тебя 👇",
                reply_markup=keyboard_return
            )
            await message.answer("🤍", reply_markup=MAIN_MENU)
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Да, поехали",
                    callback_data="start_quiz"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🤔 Расскажи подробнее",
                    callback_data="about"
                )
            ]
        ]
    )

    count = get_finished_count()
    social = f"\n🌿 Уже {count}+ человек прошли разбор\n\n" if count >= 10 else "\n\n"

    text = (
        "Привет 🤍\n\n"
        "Если тревога давно стала фоном — ты здесь по правильному адресу.\n\n"
        "Я — бот психолога Евы Левиной.\n\n"
        "За 5 минут мы разберём:\n\n"
        "🔸 какой у тебя тип тревоги\n"
        "🔸 откуда она берётся\n"
        "🔸 одно упражнение, которое поможет уже сегодня\n\n"
        "Это не тест из интернета.\n"
        f"Внутри — методика, по которой я веду клиентов в живой терапии.{social}"
        "Готова начать?"
    )

    await message.answer_photo(
        photo=FSInputFile(os.path.join(BASE_DIR, "images", "welcome.png")),
        caption=text,
        reply_markup=keyboard
    )

    await message.answer("🤍", reply_markup=MAIN_MENU)


# ---------------- RETURNING BUY ----------------

@router.callback_query(F.data == "returning_buy")
async def returning_buy(callback: CallbackQuery):

    from yookassa_payment import create_payment_returning

    await callback.answer()
    await callback.message.answer("Секунду, создаю ссылку на оплату... 🤍")

    loop = asyncio.get_event_loop()
    user_id = callback.from_user.id
    payment_url, price = await loop.run_in_executor(
        None, lambda: create_payment_returning(user_id)
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"💳 Оплатить {price}₽", url=payment_url)],
            [InlineKeyboardButton(text="✅ Я оплатил(а)", callback_data="paid")],
            [InlineKeyboardButton(text="🤔 Подумать ещё", callback_data="think")],
            [InlineKeyboardButton(text="📄 Условия оферты", url="https://levinaeva.com/oferta.html")],
        ]
    )

    await callback.message.answer(
        "Вот твоя ссылка 👇",
        reply_markup=keyboard
    )


# ---------------- UNSUBSCRIBE ----------------

@router.callback_query(F.data == "unsubscribe")
async def unsubscribe_handler(callback: CallbackQuery):
    set_unsubscribed(callback.from_user.id)
    await callback.answer()
    await callback.message.answer(
        "Хорошо, больше не буду писать 🤍\n\n"
        "Если захочешь вернуться — просто напиши /start"
    )


# ---------------- ABOUT ----------------

@router.callback_query(F.data == "about")
async def about(callback: CallbackQuery):

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Поехали",
                    callback_data="start_quiz"
                )
            ]
        ]
    )

    text = (
        "Окей, по-честному 👇\n\n"

        "📍 Что внутри:\n"
        "5 коротких вопросов о том, как ты переживаешь тревогу\n\n"

        "📍 Что получишь:\n"
        "разбор твоего типа + упражнение от психолога\n\n"

        "📍 Сколько займёт:\n"
        "4–5 минут\n\n"

        "📍 Стоит:\n"
        "0 ₽\n\n"

        "Никаких «вы умрёте в 30», только рабочая психология 🤍"
    )

    save_message(callback.from_user.id, "user", "🤔 Расскажи подробнее")
    save_message(callback.from_user.id, "bot", text)

    await callback.message.answer(
        text,
        reply_markup=keyboard
    )

    await callback.answer()


# ---------------- MENU ----------------

@router.message(F.text == "📖 О проекте")
async def menu_about(message: Message):

    save_message(message.from_user.id, "user", "📖 О проекте")

    await message.answer(
        "🤍 Меня зовут Ева Левина.\n\n"

        "Я практикующий психолог.\n\n"

        "Помогаю людям справляться с тревогой, "
        "эмоциональным выгоранием, внутренним напряжением "
        "и сложностями в отношениях.\n\n"

        "Этот проект создан для того, чтобы помочь понять "
        "причины тревоги и получить первые рабочие инструменты "
        "для улучшения своего состояния.\n\n"

        "Если потребуется более глубокая работа — "
        "вы всегда можете записаться на личную консультацию 🤍"
    )


@router.message(F.text == "💬 Задать вопрос")
async def menu_question(message: Message):

    save_message(message.from_user.id, "user", "💬 Задать вопрос")

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💬 Написать Еве",
                    url="https://t.me/evalevina_psy"
                )
            ]
        ]
    )

    await message.answer(
        "Напиши мне напрямую — отвечу в ближайшее время 🤍",
        reply_markup=keyboard
    )


@router.message(Command("help"))
async def cmd_help(message: Message):

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💬 Написать Еве",
                    url="https://t.me/evalevina_psy"
                )
            ]
        ]
    )

    await message.answer(
        "🤍 Если есть вопросы — напиши мне напрямую.\n\n"
        "Я отвечу в ближайшее время.",
        reply_markup=keyboard
    )


@router.message(Command("restart"))
async def cmd_restart(message: Message, state: FSMContext):

    await state.clear()

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Да, поехали",
                    callback_data="start_quiz"
                )
            ]
        ]
    )

    await message.answer(
        "Начинаем заново 🔄\n\n"
        "Готова пройти разбор?",
        reply_markup=keyboard
    )


@router.message(Command("mytype"))
async def cmd_mytype(message: Message):

    profile = get_user_profile(message.from_user.id)

    if not profile or not profile[1]:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="✅ Пройти тест", callback_data="start_quiz")]
            ]
        )
        await message.answer(
            "Ты ещё не прошла разбор 🤍\n\n"
            "Пройди — займёт 4–5 минут.",
            reply_markup=keyboard
        )
        return

    first_name, anxiety_type, bought, finished = profile
    type_label = TYPE_LABELS.get(anxiety_type, "")

    status = "✅ Разбор куплен" if bought else "📋 Разбор не куплен"

    await message.answer(
        f"Твой тип тревоги: *{type_label}*\n\n"
        f"{status}\n\n"
        f"Используй меню ниже для дневника, AI-помощника или записи на сессию 🤍",
        parse_mode="Markdown"
    )
