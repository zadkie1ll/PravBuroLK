from __future__ import annotations

from urllib.parse import quote

from ..config import settings
from .phone_insights import normalize_russian_phone_digits

WHATSAPP_FOLLOWUP_MESSAGE = (
    "Добрый день! Вы хотели получить консультацию по списанию долга, но дозвониться до вас не смогли. "
    "Прикрепляю видео, в котором наш руководитель, Станислав Свириденко, рассказывает, что вы получите "
    "из консультации с нами. Посмотрите его и напишите, когда вам удобно созвониться😺 "
    "https://vk.com/video-211710764_456239939?list=ln-9eixjJMj2MwydO91XY"
)
MAX_FOLLOWUP_MESSAGE = WHATSAPP_FOLLOWUP_MESSAGE


def build_whatsapp_followup_url(phone: str) -> str:
    digits = normalize_russian_phone_digits(phone)
    if not digits:
        return ""
    return f"whatsapp://send?phone={digits}&text={quote(WHATSAPP_FOLLOWUP_MESSAGE, safe='')}"


def build_whatsapp_followup_web_url(phone: str) -> str:
    digits = normalize_russian_phone_digits(phone)
    if not digits:
        return ""
    return f"https://web.whatsapp.com/send?phone={digits}&text={quote(WHATSAPP_FOLLOWUP_MESSAGE, safe='')}"


def build_whatsapp_desktop_url(phone: str) -> str:
    digits = normalize_russian_phone_digits(phone)
    return f"whatsapp://send?phone={digits}" if digits else ""


def build_telegram_desktop_url(phone: str) -> str:
    digits = normalize_russian_phone_digits(phone)
    return f"tg://resolve?phone={digits}" if digits else ""


def build_max_desktop_url() -> str:
    return settings.call_queue_max_desktop_url or "max://"


def build_max_followup_url() -> str:
    return f"https://max.ru/:share?text={quote(MAX_FOLLOWUP_MESSAGE, safe='')}"


def with_social_desktop_links(item: dict) -> dict:
    phone = item.get("phone", "")
    return {
        **item,
        "whatsapp_followup_url": build_whatsapp_followup_url(phone),
        "whatsapp_followup_web_url": build_whatsapp_followup_web_url(phone),
        "whatsapp_desktop_url": build_whatsapp_desktop_url(phone),
        "telegram_desktop_url": build_telegram_desktop_url(phone),
        "max_desktop_url": build_max_desktop_url(),
        "max_followup_url": build_max_followup_url(),
    }
