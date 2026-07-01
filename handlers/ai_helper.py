from anthropic import AsyncAnthropic
from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.enums import ChatAction

from config import ANTHROPIC_API_KEY
from database import save_message, get_ai_history, get_user_type
from keyboards import MAIN_MENU as KEYBOARDS_MAIN_MENU

router = Router()

client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

CRISIS_KEYWORDS = [
    "не хочу жить", "не хочется жить", "хочу умереть",
    "убью себя", "убить себя", "покончить с собой",
    "суицид", "суицидальн", "нет смысла жить",
    "жить не хочу", "лучше умереть", "не хочу больше жить",
    "прыгну", "порежу вены", "повешусь", "повеситься",
    "выпрыгну", "наглотаюсь", "выпью таблетки",
    "нет смысла", "незачем жить", "хочу уйти навсегда"
]

HOTLINES_MESSAGE = (
    "🆘 Я слышу тебя. То, что ты сейчас переживаешь — это очень серьёзно, "
    "и ты не одна(один) с этим.\n\n"
    "Пожалуйста, позвони прямо сейчас:\n\n"
    "📞 8-800-2000-122\n"
    "Телефон доверия — бесплатно, круглосуточно, вся Россия\n\n"
    "📞 112 — Скорая помощь\n\n"
    "📞 8-800-100-49-94\n"
    "Центр экстренной психологической помощи МЧС\n\n"
    "Рядом всегда есть люди, которые помогут 🤍"
)

_BASE_PROMPT = (
    "Ты — опытный психолог с 20-летним стажем работы. "
    "Ты ведёшь тёплый, поддерживающий диалог с клиентом на русском языке. "
    "Говори с заботой и эмпатией, используй мягкий тон. "
    "Задавай уточняющие вопросы, помогай клиенту разобраться в своих чувствах. "
    "Не давай медицинских советов и не ставь диагнозов. "
    "Валидируй чувства клиента — дай понять, что его переживания важны и нормальны. "
    "Если клиент упоминает мысли о суициде или самоповреждении — "
    "прояви максимальную заботу, скажи что он/она не одинок(а), "
    "и что важно обратиться за помощью к живому специалисту или на горячую линию. "
    "Отвечай умеренно по объёму — не слишком кратко и не слишком длинно. "
    "Никогда не выходи из роли психолога."
)

_TYPE_DESCRIPTIONS = {
    "A": (
        "Сканер — постоянно сканирует окружение на угрозу, очень чувствителен(а) "
        "к настроению других людей и интонациям, устаёт от новых мест и людей, "
        "часто имеет головные боли и напряжение в глазах и голове."
    ),
    "B": (
        "Катастрофист — строит катастрофические сценарии, живёт в воображаемом плохом будущем, "
        "часто беспокоится о здоровье и близких, плохо спит, испытывает хроническую усталость."
    ),
    "C": (
        "Замиратель — в стрессе замирает и не может действовать, "
        "трудно говорить «нет» и отстаивать границы, копит обиды, "
        "иногда чувствует себя как бы наблюдающей за своей жизнью со стороны."
    ),
    "D": (
        "Контролёр — пытается всё контролировать и предусмотреть, "
        "тяжело делегировать и отпускать, испытывает хроническое напряжение в теле, "
        "трудно отдыхать, склонен(на) к выгоранию."
    ),
}


def _build_system_prompt(anxiety_type=None):
    if not anxiety_type or anxiety_type not in _TYPE_DESCRIPTIONS:
        return _BASE_PROMPT
    type_info = _TYPE_DESCRIPTIONS[anxiety_type]
    return (
        _BASE_PROMPT
        + f"\n\nВАЖНО: по результатам теста этот клиент — {type_info} "
        "Используй это знание, чтобы точнее понимать его реакции и давать более "
        "персонализированную поддержку. Можешь мягко упоминать связь между "
        "переживаниями клиента и его типом тревоги, если это уместно."
    )

MAIN_MENU = KEYBOARDS_MAIN_MENU


class AIState(StatesGroup):
    chatting = State()


def detect_crisis(text: str) -> bool:
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in CRISIS_KEYWORDS)


@router.message(F.text == "🤖 AI - помощник")
async def start_ai_chat(message: Message, state: FSMContext):
    user_id = message.from_user.id
    anxiety_type = get_user_type(user_id)
    system_prompt = _build_system_prompt(anxiety_type)

    await state.set_state(AIState.chatting)
    await state.update_data(system_prompt=system_prompt)

    exit_kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Завершить диалог")]],
        resize_keyboard=True
    )

    await message.answer(
        "Привет 🤍\n\n"
        "Я здесь, чтобы выслушать тебя и поддержать.\n\n"
        "Расскажи, что тебя беспокоит?",
        reply_markup=exit_kb
    )


@router.message(F.text == "❌ Завершить диалог", AIState.chatting)
async def exit_ai_chat(message: Message, state: FSMContext):
    await state.clear()

    await message.answer(
        "Диалог завершён 🤍\n\nБереги себя. Если понадоблюсь — нажми «🤖 AI - помощник».",
        reply_markup=MAIN_MENU
    )


@router.message(AIState.chatting)
async def process_ai_message(message: Message, state: FSMContext):
    user_id = message.from_user.id
    user_text = message.text

    if detect_crisis(user_text):
        await message.answer(HOTLINES_MESSAGE)

    # Сохраняем сообщение пользователя в БД
    save_message(user_id, "ai_user", user_text)

    # Загружаем историю из БД (последние 20 сообщений)
    history = get_ai_history(user_id, limit=20)

    data = await state.get_data()
    system_prompt = data.get("system_prompt", _BASE_PROMPT)

    try:
        await message.bot.send_chat_action(
            chat_id=message.chat.id,
            action=ChatAction.TYPING
        )

        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=system_prompt,
            messages=history
        )

        ai_reply = response.content[0].text

        # Сохраняем ответ бота в БД
        save_message(user_id, "ai_bot", ai_reply)

        await message.answer(ai_reply)

    except Exception as e:
        print(f"AI error: {e}")
        await message.answer("Произошла ошибка. Попробуй написать ещё раз 🤍")
