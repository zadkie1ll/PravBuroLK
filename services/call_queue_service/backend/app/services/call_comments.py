from __future__ import annotations

from datetime import datetime, timezone as dt_timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ..config import settings


def get_call_queue_timezone() -> ZoneInfo:
    try:
        return ZoneInfo(settings.call_queue_bitrix_time_zone or "Europe/Moscow")
    except ZoneInfoNotFoundError:
        return ZoneInfo("Europe/Moscow")


def get_call_queue_localdate():
    return datetime.now(dt_timezone.utc).astimezone(get_call_queue_timezone()).date()


def get_manager_short_name(manager_name: str) -> str:
    raw_name = (manager_name or "").strip()
    if not raw_name:
        return "Менеджер"
    return raw_name.split()[0]


def format_unanswered_comment(manager_name: str) -> str:
    return f"{get_call_queue_localdate():%d.%m} ({get_manager_short_name(manager_name)}) недозвон"


def format_unavailable_comment(manager_name: str) -> str:
    return f"{get_call_queue_localdate():%d.%m} ({get_manager_short_name(manager_name)}) номер недоступен"


def format_voicemail_comment(manager_name: str) -> str:
    return f"{get_call_queue_localdate():%d.%m} ({get_manager_short_name(manager_name)}) автоответчик"
