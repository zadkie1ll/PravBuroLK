from __future__ import annotations

from datetime import date
from io import BytesIO
import random
import uuid
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.utils.text import slugify
from PIL import Image, ImageDraw, ImageFont

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


def persist_generated_assets(greeting: March8Greeting, regenerate: bool = False) -> March8Greeting:
    changed_fields: list[str] = []
    slug_name = slugify(greeting.recipient_name or "pozdravlenie", allow_unicode=True) or "pozdravlenie"
    unique_suffix = uuid.uuid4().hex[:8]

    if regenerate or not greeting.astrology_image:
        img_bytes = build_astrology_image_bytes(greeting)
        img_name = f"{slug_name}-{unique_suffix}-astro.png"
        greeting.astrology_image.save(img_name, ContentFile(img_bytes), save=False)
        changed_fields.append("astrology_image")

    if changed_fields:
        changed_fields.append("updated_at")
        greeting.save(update_fields=changed_fields)
    return greeting
