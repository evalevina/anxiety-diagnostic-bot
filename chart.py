import os
import time
from datetime import datetime
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_REGULAR = os.path.join(BASE_DIR, "fonts", "DejaVuSans.ttf")
FONT_BOLD = os.path.join(BASE_DIR, "fonts", "DejaVuSans-Bold.ttf")

# Бренд-палитра — та же, что на лендинге и в юридических документах
# (variables --black/--accent/--soft/--line в privacy.html, oferta.html).
BG = (250, 250, 248)
INK = (17, 17, 17)
INK_SECONDARY = (85, 85, 85)
INK_MUTED = (136, 136, 136)
GRID = (229, 224, 218)
ACCENT = (156, 132, 105)

# Рендерим в 2x и уменьшаем в конце — дешёвый способ получить сглаживание
# без дополнительных библиотек.
SCALE = 2
W, H = 1000 * SCALE, 560 * SCALE
PAD_LEFT, PAD_RIGHT, PAD_TOP, PAD_BOTTOM = 70 * SCALE, 50 * SCALE, 100 * SCALE, 80 * SCALE


def _font(path, size):
    return ImageFont.truetype(path, size * SCALE)


def render_diary_chart(history, days=30):
    """history — список (score, note, created_at), отсортированный по времени.
    Возвращает PNG-байты или None, если данных нет."""

    if not history:
        return None

    now = int(time.time())
    window_start = now - days * 86400

    points = [(ts, score) for score, _, ts in history if ts >= window_start]
    if not points:
        return None

    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img, "RGBA")

    plot_left = PAD_LEFT
    plot_right = W - PAD_RIGHT
    plot_top = PAD_TOP
    plot_bottom = H - PAD_BOTTOM
    plot_w = plot_right - plot_left
    plot_h = plot_bottom - plot_top

    def x_for(ts):
        span = max(now - window_start, 1)
        return plot_left + (ts - window_start) / span * plot_w

    def y_for(score):
        return plot_bottom - (score / 10) * plot_h

    # ── Заголовок ──
    title_font = _font(FONT_BOLD, 26)
    sub_font = _font(FONT_REGULAR, 15)
    draw.text((plot_left, 28 * SCALE), f"Твоя тревога за {days} дней", font=title_font, fill=INK)

    avg = sum(s for _, s in points) / len(points)
    if len(points) >= 2:
        mid = len(points) // 2
        first_half_avg = sum(s for _, s in points[:mid]) / mid
        second_half_avg = sum(s for _, s in points[mid:]) / (len(points) - mid)
        diff = second_half_avg - first_half_avg
        if diff <= -1:
            trend = "тревога идёт на спад ↓"
        elif diff >= 1:
            trend = "сейчас потревожнее, чем обычно ↑"
        else:
            trend = "уровень стабильный →"
    else:
        trend = "первая запись — начало графика"

    draw.text(
        (plot_left, 60 * SCALE),
        f"Записей: {len(points)} · средний уровень: {avg:.1f} · {trend}",
        font=sub_font, fill=INK_SECONDARY
    )

    # ── Гридлайны и подписи Y (чистые числа: 2,4,6,8,10) ──
    tick_font = _font(FONT_REGULAR, 14)
    for tick in (2, 4, 6, 8, 10):
        y = y_for(tick)
        draw.line([(plot_left, y), (plot_right, y)], fill=GRID, width=1 * SCALE)
        tw = draw.textlength(str(tick), font=tick_font)
        draw.text((plot_left - 14 * SCALE - tw, y - 8 * SCALE), str(tick), font=tick_font, fill=INK_MUTED)

    # Базовая линия (0) чуть заметнее гридлайнов
    draw.line([(plot_left, plot_bottom), (plot_right, plot_bottom)], fill=GRID, width=1 * SCALE)

    # ── Средний уровень — пунктирная опорная линия ──
    avg_y = y_for(avg)
    dash = 6 * SCALE
    x = plot_left
    while x < plot_right:
        draw.line([(x, avg_y), (min(x + dash, plot_right), avg_y)], fill=INK_MUTED, width=1 * SCALE)
        x += dash * 2
    avg_label = f"Средний {avg:.1f}"
    alw = draw.textlength(avg_label, font=tick_font)
    draw.text((plot_right - alw, avg_y - 22 * SCALE), avg_label, font=tick_font, fill=INK_MUTED)

    # ── Линия тренда + заливка ──
    coords = [(x_for(ts), y_for(score)) for ts, score in points]

    if len(coords) >= 2:
        fill_poly = [(coords[0][0], plot_bottom)] + coords + [(coords[-1][0], plot_bottom)]
        draw.polygon(fill_poly, fill=ACCENT + (26,))
        draw.line(coords, fill=ACCENT, width=4 * SCALE, joint="curve")

    marker_r = 6 * SCALE
    ring_r = marker_r + 3 * SCALE
    for cx, cy in coords:
        draw.ellipse([cx - ring_r, cy - ring_r, cx + ring_r, cy + ring_r], fill=BG)
        draw.ellipse([cx - marker_r, cy - marker_r, cx + marker_r, cy + marker_r], fill=ACCENT)

    # ── Подпись последней точки ──
    last_x, last_y = coords[-1]
    end_font = _font(FONT_BOLD, 16)
    end_label = str(points[-1][1])
    draw.text((last_x + 12 * SCALE, last_y - 10 * SCALE), end_label, font=end_font, fill=INK)

    # ── Подписи дат по оси X (первая, средняя, последняя точки окна) ──
    date_font = _font(FONT_REGULAR, 14)
    for ts in (window_start, (window_start + now) // 2, now):
        x = x_for(ts)
        label = datetime.fromtimestamp(ts).strftime("%d.%m")
        tw = draw.textlength(label, font=date_font)
        tx = min(max(x - tw / 2, plot_left), plot_right - tw)
        draw.text((tx, plot_bottom + 14 * SCALE), label, font=date_font, fill=INK_MUTED)

    img = img.resize((W // SCALE, H // SCALE), Image.LANCZOS)

    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
