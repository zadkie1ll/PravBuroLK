from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from typing import Any

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

BITRIX_WEBHOOK_URL = getattr(
    settings,
    "BITRIX_WEBHOOK_URL",
    "https://prav-buro.bitrix24.ru/rest/24/pa1x5irnfpbcnh27/",
).rstrip("/")
MEGAFON_VATS_WEBHOOK_URL = getattr(settings, "MEGAFON_VATS_WEBHOOK_URL", "")
LAWYER_INFO_CACHE_TTL = int(getattr(settings, "LAWYER_INFO_CACHE_TTL", 300))


@dataclass
class LawyerInfo:
    first_name: str = ""
    last_name: str = ""
    email: str = ""
    phone: str = ""
    avatar_url: str = ""

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def get_client_lawyer_info(bitrix_deal_id: str | int | None) -> dict[str, str] | None:
    """
    Возвращает данные сопровождающего юриста клиента:
    - имя/фамилия/email из Bitrix ответственного по сделке
    - телефон из webhook Мегафона по имени + фамилии
    - avatar_url из поля отчества (если там URL) либо из Bitrix-фото
    """
    if not bitrix_deal_id:
        return None

    cache_key = f"client-lawyer-info:{bitrix_deal_id}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        info = _fetch_lawyer_info(bitrix_deal_id)
    except Exception:
        logger.exception("Failed to load lawyer info for deal %s", bitrix_deal_id)
        info = None

    cache.set(cache_key, info, LAWYER_INFO_CACHE_TTL)
    return info


def _fetch_lawyer_info(bitrix_deal_id: str | int) -> dict[str, str] | None:
    deal = _bitrix_call("crm.deal.get", {"ID": bitrix_deal_id})
    assigned_by_id = (deal or {}).get("ASSIGNED_BY_ID")
    if not assigned_by_id:
        return None

    users = _bitrix_call("user.get", {"filter": {"ID": assigned_by_id}})
    if not users:
        return None

    user = users[0]
    first_name = str(user.get("NAME") or "").strip()
    last_name = str(user.get("LAST_NAME") or "").strip()
    email = str(user.get("EMAIL") or "").strip()

    middle_raw = str(user.get("SECOND_NAME") or "").strip()
    avatar_url = middle_raw if _is_url(middle_raw) else ""

    if not avatar_url:
        personal_photo = user.get("PERSONAL_PHOTO")
        if _is_url(personal_photo):
            avatar_url = str(personal_photo)

    megafon_row = _fetch_employee_from_megafon(first_name, last_name)
    phone = _extract_phone(megafon_row)
    if not avatar_url:
        avatar_url = _extract_avatar_url(megafon_row) or ""

    info = LawyerInfo(
        first_name=first_name,
        last_name=last_name,
        email=email,
        phone=phone,
        avatar_url=avatar_url,
    )
    return info.as_dict()


def _bitrix_call(method: str, params: dict[str, Any]) -> Any:
    url = f"{BITRIX_WEBHOOK_URL}/{method}.json"
    response = requests.get(url, params=params, timeout=15)
    response.raise_for_status()
    payload = response.json()
    if payload.get("error"):
        raise RuntimeError(f"Bitrix error: {payload.get('error_description') or payload['error']}")
    return payload.get("result")


def _fetch_employee_from_megafon(first_name: str, last_name: str) -> dict[str, Any] | None:
    if not MEGAFON_VATS_WEBHOOK_URL or not first_name or not last_name:
        return None

    payload = {
        "first_name": first_name,
        "last_name": last_name,
        "name": first_name,
        "surname": last_name,
    }

    try:
        response = requests.post(MEGAFON_VATS_WEBHOOK_URL, json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()
    except Exception:
        logger.exception("Megafon VATS webhook request failed")
        return None

    return _find_employee_row(data, first_name, last_name)


def _extract_phone(row: dict[str, Any] | None) -> str:
    if not row:
        return ""
    for key in ("phone", "phone_number", "number", "PHONE", "work_phone", "personal_phone"):
        value = row.get(key)
        if value:
            return str(value).strip()
    return ""


def _extract_avatar_url(row: dict[str, Any] | None) -> str:
    if not row:
        return ""
    # По задаче ссылка на аватар может приходить в поле отчества.
    for key in ("otchestvo", "patronymic", "middle_name", "middlename", "SECOND_NAME"):
        value = row.get(key)
        if _is_url(value):
            return str(value).strip()

    for key in ("avatar", "avatar_url", "photo", "photo_url"):
        value = row.get(key)
        if _is_url(value):
            return str(value).strip()
    return ""


def _find_employee_row(data: Any, first_name: str, last_name: str) -> dict[str, Any] | None:
    target_first = _normalize_name(first_name)
    target_last = _normalize_name(last_name)

    rows: list[dict[str, Any]] = []

    if isinstance(data, list):
        rows = [item for item in data if isinstance(item, dict)]
    elif isinstance(data, dict):
        for key in ("result", "data", "employees", "items"):
            chunk = data.get(key)
            if isinstance(chunk, list):
                rows = [item for item in chunk if isinstance(item, dict)]
                break
        if not rows:
            rows = [data]

    for row in rows:
        row_first = _normalize_name(
            row.get("first_name")
            or row.get("name")
            or row.get("NAME")
            or row.get("имя")
        )
        row_last = _normalize_name(
            row.get("last_name")
            or row.get("surname")
            or row.get("LAST_NAME")
            or row.get("фамилия")
        )

        if row_first == target_first and row_last == target_last:
            return row

    return None


def _normalize_name(value: Any) -> str:
    return str(value or "").strip().lower()


def _is_url(value: Any) -> bool:
    text = str(value or "").strip()
    return text.startswith("http://") or text.startswith("https://")
