import os

from aiogram import Bot
from aiogram.types import FSInputFile

from database import get_user_type
from config import PDF_SCANNER, PDF_CATASTROPHIST, PDF_FREEZER, PDF_CONTROLLER

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

TYPE_NAMES = {
    "A": "🔍 Сканер",
    "B": "🌪 Катастрофист",
    "C": "🌫 Замиратель",
    "D": "🎯 Контролёр",
}

TYPE_PDF_LINKS = {
    "A": PDF_SCANNER,
    "B": PDF_CATASTROPHIST,
    "C": PDF_FREEZER,
    "D": PDF_CONTROLLER,
}

TYPE_INTRO = {
    "A": (
        "Внутри — всё про твой тип «Сканер» 🔍\n\n"
        "25 страниц о том, почему твоя нервная система работает как радар, "
        "как это влияет на отношения и работу, "
        "и план на 30 дней чтобы наконец выдохнуть."
    ),
    "B": (
        "Внутри — всё про твой тип «Катастрофист» 🌪\n\n"
        "25 страниц о том, почему мозг рисует худшие сценарии, "
        "как остановить этот поток, "
        "и план на 30 дней чтобы снова жить в настоящем."
    ),
    "C": (
        "Внутри — всё про твой тип «Замиратель» 🌫\n\n"
        "25 страниц о том, почему ты замираешь в важные моменты, "
        "как разморозить нервную систему, "
        "и план на 30 дней чтобы снова чувствовать себя живой."
    ),
    "D": (
        "Внутри — всё про твой тип «Контролёр» 🎯\n\n"
        "25 страниц о том, почему контроль не спасает от тревоги, "
        "как отпустить и не сломаться, "
        "и план на 30 дней чтобы наконец отдохнуть."
    ),
}


async def send_materials(bot: Bot, user_id: int):

    anxiety_type = get_user_type(user_id)
    type_name = TYPE_NAMES.get(anxiety_type, "")
    intro = TYPE_INTRO.get(anxiety_type, "Лови материалы 🤍")
    pdf_link = TYPE_PDF_LINKS.get(anxiety_type, "")

    await bot.send_message(user_id, f"Рада, что ты здесь 🤍\n\nЭто решение — про себя. Это важно.\n\n{intro}")

    # PDF: сначала пробуем персональную ссылку из .env,
    # если не настроена — отправляем файл гайда для этого типа
    if pdf_link and pdf_link != "https://example.com":
        await bot.send_message(user_id, f"📕 Твой разбор:\n{pdf_link}")
    else:
        pdf_path = os.path.join(BASE_DIR, "materials", f"razbor_{anxiety_type}.pdf")
        if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0:
            await bot.send_document(
                user_id,
                FSInputFile(pdf_path),
                caption=f"📕 Полный разбор — {type_name}" if type_name else "📕 Полный разбор"
            )

    # Аудио-медитации (свои для каждого типа тревоги)
    for i in range(1, 4):
        audio_path = os.path.join(BASE_DIR, "materials", f"audio_{anxiety_type}{i}.mp3")
        if os.path.exists(audio_path) and os.path.getsize(audio_path) > 0:
            await bot.send_audio(
                user_id,
                FSInputFile(audio_path),
                caption=f"🎧 Аудио-медитация {i}/3 — {type_name}" if type_name else f"🎧 Аудио-медитация {i}/3"
            )

    # Вебинар
    webinar_path = os.path.join(BASE_DIR, "materials", "webinar.mp4")
    if os.path.exists(webinar_path) and os.path.getsize(webinar_path) > 0:
        await bot.send_video(
            user_id,
            FSInputFile(webinar_path),
            caption="🎁 Бонус: запись вебинара «Как тревога съедает деньги и отношения»"
        )
