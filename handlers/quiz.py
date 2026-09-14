from collections import Counter

from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove
)
from aiogram.fsm.context import FSMContext

from database import save_message, save_phone, add_funnel_task, has_pending_quiz_reminder, set_started_quiz
from states.quiz_states import QuizState
from handlers.consent import ensure_consent

router = Router()


# ---------------- QUESTIONS ----------------

QUESTIONS = [

    {
        "question":
            "❓ Вопрос 1/5\n\n"
            "Как часто ты ловишь себя на тревоге? 🌀",

        "answers": [

            ("🅰️ Постоянно мониторю всё вокруг, как будто что-то проверяю", "A"),

            ("🅱️ Накатывает волнами картинок «а вдруг случится…»", "B"),

            ("🅲️ В стрессе будто застываю, ничего не могу", "C"),

            ("🅳️ Постоянно фоном, особенно когда что-то идёт не по плану", "D")
        ]
    },

    {
        "question":
            "❓ Вопрос 2/5\n\n"
            "Где тревога живёт у тебя в теле? 🫀",

        "answers": [

            ("🅰️ Напряжение в шее, глазах, голове «гудит»", "A"),

            ("🅱️ Сжимается грудь, тяжело дышать, сердце колотится", "B"),

            ("🅲️ Тяжесть, оцепенение, будто ватная", "C"),

            ("🅳️ Челюсть зажата, плечи каменные, кулаки сжаты", "D")
        ]
    },

    {
        "question":
            "❓ Вопрос 3/5\n\n"
            "Что чаще всего её запускает? ⚡️",

        "answers": [

            ("🅰️ Новые люди, незнакомые места, неопределённость", "A"),

            ("🅱️ Новости, мысли о здоровье, будущем, близких", "B"),

            ("🅲️ Конфликты, чужое недовольство, давление", "C"),

            ("🅳️ Когда что-то идёт не так, как я спланировала", "D")
        ]
    },

    {
        "question":
            "❓ Вопрос 4/5\n\n"
            "Как ты обычно справляешься? 🛟",

        "answers": [

            ("🅰️ Изучаю всё заранее, читаю отзывы, готовлюсь к любому раскладу", "A"),

            ("🅱️ Прокручиваю в голове сценарии, ищу подтверждения опасности", "B"),

            ("🅲️ Замираю, ухожу в себя, жду пока пройдёт", "C"),

            ("🅳️ Делаю списки, перепроверяю, беру всё на себя", "D")
        ]
    },

    {
        "question":
            "❓ Вопрос 5/5\n\n"
            "Что ты хочешь чувствовать вместо тревоги? 🤍",

        "answers": [

            ("🅰️ Расслабленность и доверие к миру", "A"),

            ("🅱️ Спокойствие, что «всё будет хорошо»", "B"),

            ("🅲️ Живость, силу, что я могу действовать", "C"),

            ("🅳️ Лёгкость и право отпустить контроль", "D")
        ]
    }
]


# ---------------- START QUIZ ----------------

def _phone_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Поделиться номером", request_contact=True)],
            [KeyboardButton(text="Пропустить")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )


@router.callback_query(F.data == "start_quiz")
async def start_quiz(callback: CallbackQuery, state: FSMContext):

    if not await ensure_consent(callback.message, callback.from_user.id):
        await callback.answer()
        return

    set_started_quiz(callback.from_user.id)
    save_message(callback.from_user.id, "user", "✅ Да, поехали (начал тест)")

    await state.clear()
    await state.set_state(QuizState.waiting_phone)

    # Напоминание через 2 часа если не дошла до результата (без дублей)
    if not has_pending_quiz_reminder(callback.from_user.id):
        add_funnel_task(callback.from_user.id, 2 * 3600, "quiz_reminder")

    await callback.message.answer(
        "Прежде чем начать — оставь свой номер телефона.\n\n"
        "Это поможет мне связаться с тобой, "
        "если захочешь записаться на консультацию 🤍",
        reply_markup=_phone_keyboard()
    )

    await callback.answer()


@router.message(QuizState.waiting_phone, F.contact)
async def receive_phone(message: Message, state: FSMContext):

    phone = message.contact.phone_number
    save_phone(message.from_user.id, phone)
    save_message(message.from_user.id, "user", f"📱 Номер: {phone}")

    await message.answer("Спасибо! 🤍", reply_markup=ReplyKeyboardRemove())

    await send_question(message, state, 0)


@router.message(QuizState.waiting_phone, F.text == "Пропустить")
async def skip_phone(message: Message, state: FSMContext):

    save_message(message.from_user.id, "user", "Пропустил номер телефона")

    await message.answer("Хорошо, начинаем! 🤍", reply_markup=ReplyKeyboardRemove())

    await send_question(message, state, 0)


@router.message(QuizState.waiting_phone)
async def invalid_phone_input(message: Message):
    # Что угодно, кроме контакта или точного "Пропустить" (опечатка, стикер,
    # голосовое) — раньше улетало в глобальный fallback, который сбрасывал
    # FSM-состояние и заставлял проходить тест заново. Вместо этого мягко
    # переспрашиваем, не теряя прогресс.
    await message.answer(
        "Не поняла 🤍 Поделись номером через кнопку ниже или нажми «Пропустить»,"
        " чтобы продолжить без него.",
        reply_markup=_phone_keyboard()
    )


# ---------------- SEND QUESTION ----------------

async def send_question(message, state, index):

    question_data = QUESTIONS[index]

    filled = index + 1
    progress = "▓" * filled + "░" * (5 - filled) + f"  {filled}/5\n\n"

    keyboard_buttons = []

    for text, value in question_data["answers"]:

        keyboard_buttons.append(

            [
                InlineKeyboardButton(
                    text=text,
                    callback_data=f"answer_{index}_{value}"
                )
            ]
        )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=keyboard_buttons
    )

    await message.answer(
        progress + question_data["question"],
        reply_markup=keyboard
    )


# ---------------- ANSWERS ----------------

@router.callback_query(F.data.startswith("answer_"))
async def process_answer(
    callback: CallbackQuery,
    state: FSMContext
):

    data = callback.data.split("_")

    index = int(data[1])

    answer = data[2]

    question_text = QUESTIONS[index]["question"].split("\n\n")[0]
    answer_text = next(
        (t for t, v in QUESTIONS[index]["answers"] if v == answer), answer
    )
    save_message(
        callback.from_user.id,
        "user",
        f"Вопрос {index + 1}: {answer_text}"
    )

    user_data = await state.get_data()

    answers = user_data.get("answers", [])

    answers.append(answer)

    await state.update_data(
        answers=answers
    )

    # ПРОГРЕВ

    if index == 1:

        await callback.message.answer(
            "🧠 Уже вижу интересную закономерность..."
        )

    if index == 3:

        await callback.message.answer(
            "📍 Остался последний шаг..."
        )

    # NEXT QUESTION

    if index < 4:

        await send_question(
            callback.message,
            state,
            index + 1
        )

        await callback.answer()

    else:

        # ОПРЕДЕЛЕНИЕ ТИПА

        counter = Counter(answers)

        most_common = counter.most_common()

        # ЕСЛИ ОДИН ЛИДЕР

        if len(most_common) == 1:

            result = most_common[0][0]

        else:

            first_count = most_common[0][1]

            leaders = [
                item[0]
                for item in most_common
                if item[1] == first_count
            ]

            # ЕСЛИ ПОРОВНУ — БЕРЁМ ОТВЕТ ИЗ ВОПРОСА №2

            if len(leaders) > 1:

                result = answers[1]

            else:

                result = most_common[0][0]

        secondary = most_common[1][0] if len(most_common) >= 2 else None

        await state.update_data(
            result=result,
            result_secondary=secondary
        )

        await callback.answer()

        from handlers.result import show_result

        await show_result(
            callback.message,
            state
        )