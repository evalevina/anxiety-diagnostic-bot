import asyncio
import logging
import os

logger = logging.getLogger(__name__)

from aiogram import Router, F
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    ReplyKeyboardMarkup,
    KeyboardButton,
    FSInputFile
)
from aiogram.fsm.context import FSMContext

from database import (
    update_result,
    set_thinking,
    set_bought,
    set_saw_offer,
    add_funnel_task,
    save_message,
    get_user_bought,
    get_latest_payment_id,
    has_pending_funnel_tasks,
    has_tip_tasks,
    get_user_type,
    get_referrer_id,
    has_diary_reminder_task,
    has_diary_weekly_task
)

from yookassa_payment import check_payment_status
from materials import send_materials
from keyboards import MAIN_MENU
from states.quiz_states import QuizState

router = Router()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

QUESTION_LINK = "https://t.me/evalevina_psy"

TYPE_NAMES = {
    "A": "Сканера",
    "B": "Катастрофиста",
    "C": "Замирателя",
    "D": "Контролёра",
}


# ---------------- RESULTS ----------------

RESULTS = {

    "A": {

        "name": "🔍 Твой тип: СКАНЕР",
        "image": "scanner.png",

        "text":
            "Твоя тревога — это постоянное сканирование пространства на угрозу.\n\n"

            "Ты замечаешь то, что другие просто не видят: изменившуюся интонацию, "
            "взгляд в сторону, другой тон в сообщении. Считываешь людей с одного взгляда.\n\n"

            "Что на самом деле:\n"
            "твоя нервная система живёт в режиме «радар включён 24/7». "
            "Она ищет угрозу даже там, где её нет — не потому что ты «слишком чувствительная», "
            "а потому что когда-то это было необходимо.\n\n"

            "Откуда:\n"
            "чаще всего из среды, где нужно было «считывать настроение взрослого заранее». "
            "Ты научилась читать людей раньше, чем читать буквы. "
            "Это не слабость — это адаптация.\n\n"

            "Как это проявляется сейчас:\n"
            "ты устаёшь от людей и новых мест быстрее, чем другие — мозг работает за двоих. "
            "Сложно «просто быть». "
            "Могут быть головные боли, напряжение в глазах, тревожный сон.\n\n"

            "Хорошая новость: нервная система умеет перестраиваться. "
            "Радар можно научить выключаться 🤍",

        "exercise":
            "🌿 Упражнение «Выключи радар» — на сегодня\n\n"

            "Поставь таймер на 3 минуты.\n"
            "Закрой глаза. Положи ладонь на грудь.\n\n"

            "Скажи себе:\n"
            "«сейчас мне ничего не угрожает.\n"
            "я могу выключить радар на 3 минуты».\n\n"

            "Дыши: вдох на 4 счёта, выдох на 6.\n\n"

            "Если поймала мысль «а вдруг…» — мягко верни внимание к дыханию.\n\n"

            "Делай 3 раза в день: утром, в обед, вечером.\n"
            "Через 10 дней нервная система начнёт сама понимать, "
            "что «безопасно — можно расслабиться»."
    },

    "B": {

        "name": "🌪 Твой тип: КАТАСТРОФИСТ",
        "image": "catastrophist.png",

        "text":
            "Твоя тревога — это сценарии в голове, где всё заканчивается плохо.\n\n"

            "«А если уволят», «а если разлюбит», «а если заболею»...\n"
            "Ты живёшь немного в будущем — в том, которого ещё нет.\n\n"

            "Что на самом деле:\n"
            "мозг пытается «подготовить» тебя к худшему, чтобы не было больно неожиданно. "
            "Это не паранойя — это защита, которая сформировалась когда-то давно.\n\n"

            "Откуда:\n"
            "обычно из момента, когда что-то случилось внезапно и было очень больно — "
            "болезнь, потеря, разлука. "
            "Ты решила: «больше не дам себя застать врасплох». Мозг услышал и запомнил.\n\n"

            "Как это проявляется сейчас:\n"
            "ты проживаешь катастрофу каждый день — хотя её ещё нет. "
            "Появляется хроническая усталость, тревожный сон, "
            "сложно радоваться прямо сейчас.\n\n"

            "Хорошая новость: мозг, который умеет строить сценарии — очень гибкий. "
            "Его можно научить строить другие 🤍",

        "exercise":
            "🌿 Упражнение «А что если хорошо?» — на сегодня\n\n"

            "Поймай катастрофическую мысль («а если…»).\n"
            "Запиши её.\n\n"

            "Допиши рядом 3 варианта:\n\n"

            "Что если будет хорошо?\n"
            "Что если будет нейтрально?\n"
            "Что если будет средне?\n\n"

            "Прочитай все 4.\n"
            "Спроси: «какой из них вероятнее по статистике моей жизни?»\n\n"

            "Это переучивает мозг видеть не только катастрофу.\n"
            "Через 2 недели заметишь — катастрофических мыслей станет в 2 раза меньше."
    },

    "C": {

        "name": "🌫 Твой тип: ЗАМИРАТЕЛЬ",
        "image": "freezer.png",

        "text":
            "Твоя тревога — это парализующая волна.\n\n"

            "Ты не действуешь, не говоришь, замираешь.\n"
            "Внутри — буря. Снаружи — «всё нормально».\n\n"

            "В важные моменты как будто отключаешься — а потом ругаешь себя: "
            "почему не ответила, не сделала, не сказала.\n\n"

            "Что на самом деле:\n"
            "это не слабость и не лень. Это древняя реакция нервной системы. "
            "Когда «бить» и «бежать» когда-то были небезопасны — психика выбрала третий путь: "
            "замереть. Она защищала тебя как умела.\n\n"

            "Откуда:\n"
            "часто из отношений, где было небезопасно выражать себя — "
            "раздражали, обесценивали, наказывали за эмоции. "
            "Ты научилась исчезать, чтобы не получить ещё больше. "
            "Это было умным решением — тогда.\n\n"

            "Как это проявляется сейчас:\n"
            "сложно отстаивать своё, говорить «нет», присутствовать в конфликте. "
            "Обиды накапливаются. "
            "Иногда — ощущение что наблюдаешь за своей жизнью со стороны, а не живёшь в ней.\n\n"

            "Хорошая новость: из заморозки выходят. "
            "Нервная система умеет учиться чувствовать себя в безопасности — шаг за шагом 🤍",

        "exercise":
            "🌿 Упражнение «Заземление 5-4-3-2-1» — на сегодня\n\n"

            "Когда замираешь — назови вслух:\n\n"

            "5 вещей, которые видишь\n"
            "4 звука, которые слышишь\n"
            "3 прикосновения (стул, одежда, пол)\n"
            "2 запаха\n"
            "1 вкус\n\n"

            "Это возвращает тебя в тело за 60 секунд.\n"
            "Делай каждый раз при «замирании» — нервная система научится "
            "не уходить в заморозку, а оставаться в контакте с реальностью."
    },

    "D": {

        "name": "🎯 Твой тип: КОНТРОЛЁР",
        "image": "controller.png",

        "text":
            "Твоя тревога — это попытка удержать всё под контролем.\n\n"

            "Ты заранее просчитываешь варианты, готовишься, перепроверяешь. "
            "Кажется: если всё предусмотреть — будет безопасно.\n\n"

            "Что на самом деле:\n"
            "мозг выучил уравнение «контроль = безопасность». "
            "И теперь любая мелочь не по плану — сигнал тревоги. "
            "Чем больше контролируешь — тем сильнее тревога, "
            "потому что мир в принципе непредсказуем.\n\n"

            "Откуда:\n"
            "обычно из среды, где расслабиться было опасно — "
            "или где приходилось тащить всё на себе, потому что больше некому. "
            "Ты научилась быть начеку. Это была не прихоть — это была необходимость.\n\n"

            "Как это проявляется сейчас:\n"
            "хроническое напряжение в теле, сложно отдыхать по-настоящему — даже в отпуске. "
            "Тяжело доверить что-то другим. "
            "Устаёшь — но остановиться страшно.\n\n"

            "Хорошая новость: контроль можно отпускать постепенно, не обрушивая всё сразу. "
            "И тогда появляется лёгкость, которую, возможно, давно не чувствовала 🤍",

        "exercise":
            "🌿 Упражнение «Зона невлияния» — на сегодня\n\n"

            "Возьми лист. Раздели на 2 колонки.\n\n"

            "Слева напиши всё, что тебя тревожит сейчас.\n"
            "Справа отметь: на что я реально могу повлиять?\n\n"

            "Всё, на что повлиять нельзя — обведи и скажи вслух: «это не моя зона».\n\n"

            "Делай 7 дней подряд.\n"
            "Через неделю заметишь: тревожных мыслей станет на 30–40% меньше, а тело — мягче."
    }
}


# ---------------- SHOW RESULT ----------------

async def show_result(message, state: FSMContext):

    user_data = await state.get_data()

    result = user_data.get("result")
    result_secondary = user_data.get("result_secondary")

    if not result:

        await message.answer(
            "Произошла ошибка определения результата.\n\n"
            "Пожалуйста, пройди тест заново через /start"
        )

        return

    # Проверяем до обновления — первое ли завершение теста
    is_first_completion = get_user_type(message.chat.id) is None

    update_result(
        message.chat.id,
        result
    )

    # Благодарность рефереру при первом прохождении
    if is_first_completion:
        referrer_id = get_referrer_id(message.chat.id)
        if referrer_id:
            try:
                name = message.from_user.first_name or "Подруга"
                await message.bot.send_message(
                    referrer_id,
                    f"🤍 {name} прошла разбор по твоей ссылке!\n\n"
                    f"Спасибо что делишься — это важно 🌿"
                )
            except Exception:
                pass

    # Добавляем задачи ежедневных советов если ещё нет
    if not has_tip_tasks(message.chat.id):
        for day in range(1, 8):
            add_funnel_task(message.chat.id, day * 86400, f"tip_{day}")
        add_funnel_task(message.chat.id, 30 * 86400, "retest_30d")

    # Напоминание о дневнике через 3 дня
    if not has_diary_reminder_task(message.chat.id):
        add_funnel_task(message.chat.id, 3 * 86400, "diary_reminder")

    # Еженедельный итог дневника через 7 дней
    if not has_diary_weekly_task(message.chat.id):
        add_funnel_task(message.chat.id, 7 * 86400, "diary_weekly")

    result_data = RESULTS[result]

    save_message(message.chat.id, "bot", result_data["name"])

    await message.answer(
        "🧠 Анализирую ответы..."
    )

    await asyncio.sleep(4)

    image_path = os.path.join(BASE_DIR, "images", result_data["image"])

    await message.answer_photo(
        photo=FSInputFile(image_path),
        caption=f"{result_data['name']}\n\n{result_data['text']}"
    )

    await asyncio.sleep(4)

    secondary_note = ""
    if result_secondary:
        secondary_name = TYPE_NAMES[result_secondary]
        secondary_note = (
            f"💡 Это твой доминирующий тип — тот, что проявляется сильнее всего под давлением. "
            f"Также заметны черты {secondary_name}. Чистые типы встречаются редко — смешанный профиль это норма 🤍\n\n"
        )

    await message.answer(secondary_note + result_data["exercise"])

    # ---------------- ПРОДАЖА ----------------

    set_saw_offer(message.chat.id)
    add_funnel_task(message.chat.id, 30, "show_offer")

    await message.answer("🤍", reply_markup=MAIN_MENU)


# ---------------- THINK ----------------

@router.callback_query(F.data == "think")
async def think(callback: CallbackQuery):

    save_message(callback.from_user.id, "user", "🤔 Подумать (отложил покупку)")

    set_thinking(
        callback.from_user.id
    )

    await callback.message.answer(
        "🤍 Хорошо.\n\n"

        "Я не буду давить.\n\n"

        "Но позже пришлю тебе ещё один разбор,\n"
        "который может многое объяснить."
    )

    # Добавляем задачи только если воронка ещё не запущена
    if not has_pending_funnel_tasks(callback.from_user.id):
        add_funnel_task(callback.from_user.id, 3600, "1h")
        add_funnel_task(callback.from_user.id, 24 * 3600, "24h")
        add_funnel_task(callback.from_user.id, 72 * 3600, "72h")

    await callback.answer()


# ---------------- PAID ----------------

@router.callback_query(F.data == "paid")
async def paid(callback: CallbackQuery):

    user_id = callback.from_user.id

    save_message(user_id, "user", "✅ Я оплатил(а)")

    # Если webhook уже обработал оплату — просто подтверждаем
    if get_user_bought(user_id):
        await callback.message.answer("Ты уже с нами 🎉 Проверь сообщения выше — материалы уже отправлены 🤍")
        await callback.answer()
        return

    # Проверяем статус платежа в ЮКассе
    payment_id = get_latest_payment_id(user_id)

    if not payment_id:
        await callback.message.answer(
            "Не нашла твой платёж 🤔\n\n"
            "Напиши мне напрямую — разберёмся: @evalevina_psy 🤍"
        )
        await callback.answer()
        return

    try:
        status = check_payment_status(payment_id)
    except Exception as e:
        logger.error(f"Payment check error user={user_id}: {e}")
        await callback.message.answer(
            "Не смогла проверить платёж прямо сейчас 🤔\n\n"
            "Если оплатила — напиши мне: @evalevina_psy 🤍"
        )
        await callback.answer()
        return

    if status == "succeeded":

        set_bought(user_id)
        save_message(user_id, "bot", "✅ Оплата подтверждена")

        await send_materials(callback.message.bot, user_id)

        add_funnel_task(user_id, 86400, "onboarding_day1")
        add_funnel_task(user_id, 259200, "review_3d")
        add_funnel_task(user_id, 604800, "upsell2_7d")

    else:

        await callback.message.answer(
            "Платёж ещё обрабатывается 🕐\n\n"
            "Подожди пару минут и нажми «✅ Я оплатил(а)» снова.\n\n"
            "Если оплатила, но кнопка не срабатывает — напиши мне: @evalevina_psy 🤍"
        )

    await callback.answer()


# ---------------- NO SESSION ----------------

@router.callback_query(F.data == "no_session")
async def no_session(callback: CallbackQuery):

    await callback.message.answer(
        "Хорошо 🤍\n\n"
        "Если захочешь — предложение действует 7 дней."
    )

    await callback.answer()


# ---------------- RETEST ----------------

@router.callback_query(F.data == "retest")
async def retest(callback: CallbackQuery, state: FSMContext):
    from database import set_started_quiz, has_pending_quiz_reminder, add_funnel_task as _add_task, save_message as _save_msg

    await callback.answer()

    user_id = callback.from_user.id
    set_started_quiz(user_id)
    _save_msg(user_id, "user", "🔁 Повторный тест")

    await state.clear()
    await state.set_state(QuizState.waiting_phone)

    if not has_pending_quiz_reminder(user_id):
        _add_task(user_id, 2 * 3600, "quiz_reminder")

    phone_keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Поделиться номером", request_contact=True)],
            [KeyboardButton(text="Пропустить")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

    await callback.message.answer(
        "Прежде чем начать — оставь свой номер телефона.\n\n"
        "Это поможет мне связаться с тобой, "
        "если захочешь записаться на консультацию 🤍",
        reply_markup=phone_keyboard
    )
