import asyncio
import logging
import re

import httpx
from anthropic import AsyncAnthropic
from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.enums import ChatAction

from config import ANTHROPIC_API_KEY, ANTHROPIC_PROXY_URL
from database import save_message, get_ai_history, get_user_type, get_phone
from keyboards import MAIN_MENU as KEYBOARDS_MAIN_MENU
from handlers.consent import ensure_consent

router = Router()
logger = logging.getLogger(__name__)

# Anthropic блокирует запросы с российских IP на уровне каждого запроса.
# Если задан ANTHROPIC_PROXY_URL — трафик идёт через свой туннель-ретранслятор
# в поддерживаемой стране (см. WireGuard + Squid на отдельном VPS).
_http_client = httpx.AsyncClient(proxy=ANTHROPIC_PROXY_URL) if ANTHROPIC_PROXY_URL else None

client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY, http_client=_http_client, timeout=30.0)

CRISIS_KEYWORDS = [
    # суицид / самоповреждение
    "не хочу жить", "не хочется жить", "хочу умереть",
    "убью себя", "убить себя", "покончить с собой",
    "суицид", "суицидальн", "нет смысла жить",
    "жить не хочу", "лучше умереть", "не хочу больше жить",
    "прыгну", "порежу вены", "повешусь", "повеситься",
    "выпрыгну", "наглотаюсь", "выпью таблетки",
    "нет смысла", "незачем жить", "хочу уйти навсегда",
    # угроза/жестокость по отношению к другим — реагируем так же,
    # намеренно не ловим нейтральные фразы вроде «не люблю детей/животных»
    "убью", "прибью", "зарежу", "задушу", "изобью", "покалечу",
    "хочу убить", "хочу навредить", "хочу причинить боль",
    "мучаю животных", "издеваюсь над животными", "жестоко обращаюсь",
    "мучаю детей", "издеваюсь над детьми", "бью ребёнка", "бью детей"
]

# Номера — только там, где я уверена в их актуальности. Если страна не
# определена или её нет в списке — используем безопасный запасной вариант
# (112 + международный каталог горячих линий), а не гадаем.
COUNTRY_HOTLINES = {
    "RU": (
        ["7"],  # делит префикс с Казахстаном — см. _detect_country
        "📞 8-800-2000-122\nТелефон доверия — бесплатно, круглосуточно, вся Россия\n\n"
        "📞 112 — Скорая помощь\n\n"
        "📞 8-800-100-49-94\nЦентр экстренной психологической помощи МЧС"
    ),
    "US_CA": (
        ["1"],
        "📞 988 — Suicide & Crisis Lifeline (США и Канада), бесплатно, круглосуточно\n\n"
        "📞 911 — экстренные службы"
    ),
    "UK": (
        ["44"],
        "📞 116 123 — Samaritans, бесплатно, круглосуточно\n\n"
        "📞 999 — экстренные службы"
    ),
    "DE": (
        ["49"],
        "📞 0800 111 0 111 — Telefonseelsorge, бесплатно, круглосуточно\n\n"
        "📞 112 — экстренные службы"
    ),
    "UA": (
        ["380"],
        "📞 7333 — Lifeline Ukraine, бесплатно, круглосуточно\n\n"
        "📞 112 — экстренные службы"
    ),
    "IL": (
        ["972"],
        "📞 1201 — ЭРАН (ERAN), бесплатно, круглосуточно\n\n"
        "📞 112 — экстренные службы"
    ),
}

# сначала длинные префиксы (напр. "380"), потом короткие ("1", "7") —
# иначе короткий совпадёт первым и заслонит более точный
_PREFIX_ORDER = sorted(
    ((prefix, key) for key, (prefixes, _) in COUNTRY_HOTLINES.items() for prefix in prefixes),
    key=lambda item: -len(item[0])
)

# Если телефон точно не российский, но страны нет в списке выше — не гадаем
# с конкретным номером, а даём безопасный общий вариант.
_GENERIC_NUMBERS = (
    "📞 112 — во многих странах мира это общий номер экстренных служб\n\n"
    "🌍 Найди горячую линию психологической помощи своей страны здесь: "
    "https://findahelpline.com"
)


def _detect_country(phone: str):
    if not phone:
        return None
    digits = re.sub(r"\D", "", phone)
    for prefix, key in _PREFIX_ORDER:
        if digits.startswith(prefix):
            return key
    return None


def build_hotlines_message(user_id: int) -> str:
    phone = get_phone(user_id)

    if phone:
        # телефон есть — определяем страну; если страна не распознана
        # или не покрыта списком, используем безопасный общий вариант
        # (а не российские номера, которые из-за границы могут не работать)
        country = _detect_country(phone)
        numbers = COUNTRY_HOTLINES[country][1] if country else _GENERIC_NUMBERS
    else:
        # телефона нет вообще — по умолчанию считаем текущую (российскую)
        # аудиторию, как и раньше
        numbers = COUNTRY_HOTLINES["RU"][1]

    return (
        "🆘 Я слышу тебя. То, что ты сейчас переживаешь — это очень серьёзно, "
        "и ты не одна(один) с этим.\n\n"
        "Пожалуйста, позвони прямо сейчас:\n\n"
        f"{numbers}\n\n"
        "Рядом всегда есть люди, которые помогут 🤍"
    )

_BASE_PROMPT = (
    "Ты — тёплый, эмпатичный психолог с многолетним опытом, который поддерживает "
    "клиента в переписке на русском языке. Твоя манера — как у хорошего живого "
    "специалиста: неторопливая, внимательная, без осуждения и без спешки сразу к советам.\n\n"
    "Как ты ведёшь диалог:\n"
    "— Сначала выслушай и отрази то, что услышала — перефразируй чувство или мысль клиента "
    "своими словами, прежде чем предлагать что-то ещё.\n"
    "— Задавай один уточняющий вопрос за раз, а не несколько сразу.\n"
    "— Валидируй чувства — дай понять, что переживания клиента понятны и имеют право быть, "
    "не обесценивай и не спеши разубеждать.\n"
    "— Говори тепло и по-человечески, на «ты», можно изредка использовать 🤍, "
    "но не в каждом сообщении и не более одного эмодзи за раз.\n"
    "— Не торопись сразу «чинить» или советовать — сначала помоги клиенту самому "
    "нащупать, что с ним происходит, и только потом, если уместно, мягко предложи взгляд со стороны.\n\n"
    "Что нельзя:\n"
    "— Не ставь диагнозов и не давай медицинских советов.\n"
    "— Никогда не выходи из роли психолога.\n"
    "— Не используй markdown-разметку (звёздочки *вокруг слов*, решётки, дефисы-списки и т.п.) — "
    "сообщение приходит в Telegram обычным текстом, разметка не отрисовывается и звёздочки "
    "останутся видны буквально. Пиши простым текстом, как в обычной переписке.\n\n"
    "Если клиент упоминает мысли о суициде или самоповреждении — "
    "прояви максимальную заботу, скажи что он/она не одинок(а), "
    "и что важно обратиться за помощью к живому специалисту или на горячую линию. "
    "Отвечай умеренно по объёму — не слишком кратко и не слишком длинно."
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


# Обезличивание исходящей копии перед трансграничной передачей в Claude
# (Anthropic, США). Правит только то, что летит в API — в локальной БД
# (save_message) остаётся полный исходный текст для истории клиента и CRM.
# Регулярки, не NLP: ловят структурированные данные (телефон, email) и
# явное самопредставление по имени надёжно, но не гарантируют 100% —
# имя, упомянутое не в этих двух оборотах, не поймается.
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE_RE = re.compile(r"\+?\d[\d\-\s()]{5,}\d")
_NAME_INTRO_RE = re.compile(
    r"(меня зовут|зовут меня)\s+([А-ЯЁA-Z][а-яёa-z]+)",
    re.IGNORECASE
)


def depersonalize(text: str) -> str:
    if not text:
        return text
    text = _EMAIL_RE.sub("[email]", text)
    text = _PHONE_RE.sub("[телефон]", text)
    text = _NAME_INTRO_RE.sub(lambda m: f"{m.group(1)} [имя]", text)
    return text


@router.message(F.text == "🤖 AI - компаньон")
async def start_ai_chat(message: Message, state: FSMContext):
    user_id = message.from_user.id

    if not await ensure_consent(message, user_id):
        return

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
        "Маленькая честность на старте: я — ИИ-компаньон, а не сама Ева и не дипломированный "
        "специалист 🌿 Поэтому не заменяю живую терапию или помощь врача — но я здесь, чтобы "
        "внимательно выслушать тебя и побыть рядом.\n\n"
        "Расскажи, что тебя беспокоит?",
        reply_markup=exit_kb
    )


@router.message(F.text == "❌ Завершить диалог", AIState.chatting)
async def exit_ai_chat(message: Message, state: FSMContext):
    await state.clear()

    await message.answer(
        "Диалог завершён 🤍\n\nБереги себя. Если понадоблюсь — нажми «🤖 AI - компаньон».",
        reply_markup=MAIN_MENU
    )


@router.message(AIState.chatting)
async def process_ai_message(message: Message, state: FSMContext):
    user_id = message.from_user.id
    user_text = message.text

    if not user_text:
        await message.answer("Пока умею отвечать только на текст 🤍 Напиши словами, что тебя беспокоит?")
        return

    if detect_crisis(user_text):
        await message.answer(build_hotlines_message(user_id))

    # Сохраняем сообщение пользователя в БД
    save_message(user_id, "ai_user", user_text)

    # Загружаем историю из БД (последние 20 сообщений) — полную, для
    # локального использования. Наружу в Claude уходит отдельно
    # обезличенная копия (см. depersonalize) — сама история в БД не меняется.
    history = get_ai_history(user_id, limit=20)
    history_for_api = [
        {"role": h["role"], "content": depersonalize(h["content"])}
        for h in history
    ]

    data = await state.get_data()
    system_prompt = data.get("system_prompt", _BASE_PROMPT)

    try:
        # Индикатор "печатает" не критичен — не ждём общий таймаут сессии
        # (60с), чтобы сбой здесь не задерживал обращение к Claude.
        await message.bot.send_chat_action(
            chat_id=message.chat.id,
            action=ChatAction.TYPING,
            request_timeout=5
        )
    except Exception as e:
        logger.warning("send_chat_action failed: %s", e)

    # Первый запрос через релей-туннель иногда не проходит на "холодном"
    # соединении (обрыв/таймаут), а повторный сразу проходит — поэтому
    # ретраим сами, чтобы клиент не видел ошибку и не переспрашивал.
    ai_reply = None
    last_error = None
    for attempt in range(3):
        try:
            response = await client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1024,
                system=system_prompt,
                messages=history_for_api
            )
            ai_reply = response.content[0].text.replace("*", "")
            break
        except Exception as e:
            last_error = e
            logger.warning("AI attempt %d failed: %s", attempt + 1, e)
            if attempt < 2:
                await asyncio.sleep(1.5)

    if ai_reply is None:
        logger.error("AI error after retries", exc_info=last_error)
        try:
            await message.answer("Произошла ошибка. Попробуй написать ещё раз 🤍")
        except Exception as e:
            logger.warning("Failed to send error message to user: %s", e)
        return

    # Сохраняем ответ бота в БД
    save_message(user_id, "ai_bot", ai_reply)

    try:
        await message.answer(ai_reply)
    except Exception as e:
        logger.warning("Failed to send AI reply to user: %s", e)
