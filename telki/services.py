from __future__ import annotations

from datetime import date
from io import BytesIO
import random
import textwrap
import uuid
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.utils.text import slugify
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from .models import March8Greeting


_ZODIAC_RANGES = (
    ((1, 20), "Козерог"),
    ((2, 19), "Водолей"),
    ((3, 21), "Рыбы"),
    ((4, 20), "Овен"),
    ((5, 21), "Телец"),
    ((6, 21), "Близнецы"),
    ((7, 23), "Рак"),
    ((8, 23), "Лев"),
    ((9, 23), "Дева"),
    ((10, 23), "Весы"),
    ((11, 22), "Скорпион"),
    ((12, 22), "Стрелец"),
    ((12, 32), "Козерог"),
)

_FONT_NAME = "TelkiSFPro"
_FONT_PATHS = (
    Path(settings.BASE_DIR) / "static/fonts/SF-Pro.ttf",
    Path(settings.BASE_DIR) / "static/fonts/tt-norms-medium.otf",
    Path(settings.BASE_DIR) / "static/fonts/gilroy-light.otf",
)


def get_zodiac_sign(birth_date: date) -> str:
    marker = (birth_date.month, birth_date.day)
    for (month, day), sign in _ZODIAC_RANGES:
        if marker < (month, day):
            return sign
    return "Козерог"


def get_numerology_number(birth_date: date) -> int:
    digits = "".join(c for c in birth_date.strftime("%d%m%Y") if c.isdigit())
    total = sum(int(c) for c in digits)
    while total > 9:
        total = sum(int(c) for c in str(total))
    return total


def _load_pillow_font(size: int) -> ImageFont.ImageFont:
    for font_path in _FONT_PATHS:
        if font_path.exists():
            try:
                return ImageFont.truetype(str(font_path), size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def _ensure_reportlab_font() -> str:
    if _FONT_NAME in pdfmetrics.getRegisteredFontNames():
        return _FONT_NAME

    for font_path in _FONT_PATHS:
        if font_path.exists():
            try:
                pdfmetrics.registerFont(TTFont(_FONT_NAME, str(font_path)))
                return _FONT_NAME
            except Exception:
                continue
    return "Helvetica"


def build_astrology_image_bytes(greeting: March8Greeting) -> bytes:
    width, height = 1200, 630
    img = Image.new("RGB", (width, height), "#111827")
    draw = ImageDraw.Draw(img)

    for y in range(height):
        ratio = y / height
        r = int(13 + 70 * ratio)
        g = int(20 + 20 * ratio)
        b = int(60 + 100 * ratio)
        draw.line((0, y, width, y), fill=(r, g, b))

    seed = int(str(greeting.token.int)[:8])
    rng = random.Random(seed)
    for _ in range(120):
        x = rng.randint(0, width)
        y = rng.randint(0, height)
        radius = rng.randint(1, 3)
        shade = rng.randint(180, 255)
        draw.ellipse((x, y, x + radius, y + radius), fill=(shade, shade, shade))

    zodiac = get_zodiac_sign(greeting.birth_date)
    number = get_numerology_number(greeting.birth_date)

    title_font = _load_pillow_font(68)
    body_font = _load_pillow_font(44)
    small_font = _load_pillow_font(34)

    draw.text((70, 90), "Астрологический профиль", fill="white", font=title_font)
    draw.text((70, 240), greeting.recipient_name, fill="#fde68a", font=body_font)
    draw.text((70, 330), f"Знак зодиака: {zodiac}", fill="white", font=small_font)
    draw.text((70, 390), f"Число судьбы: {number}", fill="white", font=small_font)
    draw.text((70, 500), "С 8 Марта", fill="#f9a8d4", font=body_font)

    output = BytesIO()
    img.save(output, format="PNG")
    return output.getvalue()


def _split_for_pdf(text: str, font_name: str, font_size: int, max_width: float) -> list[str]:
    lines: list[str] = []
    for paragraph in text.splitlines() or [""]:
        if not paragraph.strip():
            lines.append("")
            continue
        current = ""
        for word in paragraph.split():
            candidate = f"{current} {word}".strip()
            width = pdfmetrics.stringWidth(candidate, font_name, font_size)
            if width <= max_width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                # Если слово очень длинное, разбиваем принудительно.
                if pdfmetrics.stringWidth(word, font_name, font_size) > max_width:
                    for chunk in textwrap.wrap(word, 20):
                        lines.append(chunk)
                    current = ""
                else:
                    current = word
        if current:
            lines.append(current)
    return lines


def build_certificate_pdf_bytes(greeting: March8Greeting) -> bytes:
    font_name = _ensure_reportlab_font()
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    page_w, page_h = A4

    if greeting.custom_background and greeting.custom_background.name:
        try:
            c.drawImage(
                ImageReader(greeting.custom_background.path),
                0,
                0,
                width=page_w,
                height=page_h,
                preserveAspectRatio=True,
                mask="auto",
            )
        except Exception:
            pass
    else:
        c.setFillColorRGB(0.96, 0.90, 0.96)
        c.rect(0, 0, page_w, page_h, fill=1, stroke=0)

    c.setFillColorRGB(0.13, 0.12, 0.23)
    c.setFont(font_name, 34)
    c.drawCentredString(page_w / 2, page_h - 120, "Сертификат поздравления")

    c.setFont(font_name, 28)
    c.setFillColorRGB(0.37, 0.17, 0.34)
    c.drawCentredString(page_w / 2, page_h - 180, "С 8 Марта")

    c.setFillColorRGB(0.05, 0.05, 0.12)
    c.setFont(font_name, 20)
    c.drawCentredString(page_w / 2, page_h - 250, greeting.recipient_name)

    zodiac = get_zodiac_sign(greeting.birth_date)
    number = get_numerology_number(greeting.birth_date)

    c.setFont(font_name, 14)
    c.drawCentredString(
        page_w / 2,
        page_h - 285,
        f"Знак зодиака: {zodiac}   |   Число судьбы: {number}",
    )

    left = 80
    right = page_w - 80
    text_box_top = page_h - 330
    line_h = 20
    c.setFont(font_name, 13)

    lines = _split_for_pdf(greeting.personal_text, font_name, 13, right - left)
    y = text_box_top
    for line in lines:
        if y < 120:
            break
        c.drawString(left, y, line)
        y -= line_h

    c.setFont(font_name, 12)
    c.setFillColorRGB(0.3, 0.3, 0.4)
    c.drawString(left, 70, "С любовью, команда ПравБюро")

    c.showPage()
    c.save()
    return buffer.getvalue()


def persist_generated_assets(greeting: March8Greeting, regenerate: bool = False) -> March8Greeting:
    changed_fields: list[str] = []
    slug_name = slugify(greeting.recipient_name or "pozdravlenie", allow_unicode=True) or "pozdravlenie"
    unique_suffix = uuid.uuid4().hex[:8]

    if regenerate or not greeting.astrology_image:
        img_bytes = build_astrology_image_bytes(greeting)
        img_name = f"{slug_name}-{unique_suffix}-astro.png"
        greeting.astrology_image.save(img_name, ContentFile(img_bytes), save=False)
        changed_fields.append("astrology_image")

    if regenerate or not greeting.certificate_pdf:
        pdf_bytes = build_certificate_pdf_bytes(greeting)
        pdf_name = f"{slug_name}-{unique_suffix}-8marta.pdf"
        greeting.certificate_pdf.save(pdf_name, ContentFile(pdf_bytes), save=False)
        changed_fields.append("certificate_pdf")

    if changed_fields:
        changed_fields.append("updated_at")
        greeting.save(update_fields=changed_fields)
    return greeting
