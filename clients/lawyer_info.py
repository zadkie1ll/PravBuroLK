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
MEGAFON_VATS_WEBHOOK_URL = "https://vats671653.megapbx.ru/crmapi/v1"
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


def get_client_lawyer_info(
    bitrix_deal_id: str | int | None,
    include_debug: bool = False,
    force_refresh: bool = False,
) -> dict[str, Any] | None:
    """
    Возвращает данные сопровождающего юриста клиента:
    - имя/фамилия/email из Bitrix ответственного по сделке
    - телефон из webhook Мегафона по имени + фамилии
    - avatar_url из поля отчества (если там URL) либо из Bitrix-фото
    """
    debug_steps: list[str] = []
    if not bitrix_deal_id:
        debug_steps.append("Client.bitrix_id пустой: нельзя получить сделку в Bitrix")
        return {"info": None, "debug_steps": debug_steps} if include_debug else None

    cache_key = f"client-lawyer-info:{bitrix_deal_id}"
    if not force_refresh:
        cached = cache.get(cache_key)
        if cached is not None:
            debug_steps.append("Данные взяты из cache")
            return {"info": cached, "debug_steps": debug_steps} if include_debug else cached

    try:
        info = _fetch_lawyer_info(bitrix_deal_id, debug_steps=debug_steps)
    except Exception as exc:
        logger.exception("Failed to load lawyer info for deal %s", bitrix_deal_id)
        debug_steps.append(f"Критическая ошибка: {exc}")
        info = None

    cache.set(cache_key, info, LAWYER_INFO_CACHE_TTL)
    return {"info": info, "debug_steps": debug_steps} if include_debug else info


def _fetch_lawyer_info(bitrix_deal_id: str | int, debug_steps: list[str] | None = None) -> dict[str, str] | None:
    debug_steps = debug_steps if debug_steps is not None else []
    debug_steps.append(f"Шаг 1: запрос сделки crm.deal.get по ID={bitrix_deal_id}")
    deal = _bitrix_call("crm.deal.get", {"ID": bitrix_deal_id})
    debug_steps.append("Шаг 1 OK: сделка получена")

    assigned_by_id = (deal or {}).get("ASSIGNED_BY_ID")
    if not assigned_by_id:
        debug_steps.append("Шаг 2 FAIL: в сделке нет ASSIGNED_BY_ID")
        return None

    debug_steps.append(f"Шаг 2: найден ASSIGNED_BY_ID={assigned_by_id}, запрашиваем user.get")
    # Для user.get фильтр через вложенный dict может быть проигнорирован.
    # Передаем filter[ID] в плоском виде, чтобы Bitrix точно отфильтровал пользователя.
    users = _bitrix_call("user.get", {"filter[ID]": assigned_by_id})
    if not users:
        debug_steps.append("Шаг 2 FAIL: user.get вернул пустой список")
        return None

    user = None
    assigned_by_id_str = str(assigned_by_id).strip()
    for candidate in users:
        if str(candidate.get("ID", "")).strip() == assigned_by_id_str:
            user = candidate
            break
    if user is None:
        user = users[0]
        debug_steps.append(
            "Шаг 2 WARN: точное совпадение user.ID с ASSIGNED_BY_ID не найдено, взят первый элемент"
        )

    debug_steps.append(
        f"Шаг 2: выбран user.ID='{user.get('ID', '')}', всего записей user.get={len(users)}"
    )
    first_name = str(user.get("NAME") or "").strip()
    last_name = str(user.get("LAST_NAME") or "").strip()
    email = str(user.get("EMAIL") or "").strip()
    debug_steps.append(
        "Шаг 2 OK: из Bitrix user получены "
        f"NAME='{first_name}', LAST_NAME='{last_name}', EMAIL='{email}'"
    )

    middle_raw = str(user.get("SECOND_NAME") or "").strip()
    avatar_url = middle_raw if _is_url(middle_raw) else ""
    if avatar_url:
        debug_steps.append("Шаг 3: avatar_url взят из SECOND_NAME (отчество)")
    else:
        debug_steps.append("Шаг 3: SECOND_NAME не содержит URL аватара")

    if not avatar_url:
        personal_photo = user.get("PERSONAL_PHOTO")
        if _is_url(personal_photo):
            avatar_url = str(personal_photo)
            debug_steps.append("Шаг 3: avatar_url взят из PERSONAL_PHOTO")

    debug_steps.append("Шаг 4: запрос в Megafon VATS webhook по имени/фамилии")
    megafon_row = _fetch_employee_from_megafon(first_name, last_name, debug_steps=debug_steps)
    phone = _extract_phone(megafon_row)
    if phone:
        debug_steps.append(f"Шаг 4 OK: найден телефон '{phone}'")
    else:
        debug_steps.append("Шаг 4: телефон не найден в ответе Мегафона")

    if not avatar_url:
        avatar_url = _extract_avatar_url(megafon_row) or ""
        if avatar_url:
            debug_steps.append("Шаг 5: avatar_url взят из ответа Мегафона")
        else:
            debug_steps.append("Шаг 5: avatar_url не найден в Мегафоне")

    info = LawyerInfo(
        first_name=first_name,
        last_name=last_name,
        email=email,
        phone=phone,
        avatar_url=avatar_url,
    )
    debug_steps.append("Итог: профиль юриста собран")
    return info.as_dict()


def _bitrix_call(method: str, params: dict[str, Any]) -> Any:
    url = f"{BITRIX_WEBHOOK_URL}/{method}.json?"
    response = requests.get(url, params=params, timeout=15)
    response.raise_for_status()
    payload = response.json()
    if payload.get("error"):
        raise RuntimeError(f"Bitrix error: {payload.get('error_description') or payload['error']}")
    return payload.get("result")


def _fetch_employee_from_megafon(
    first_name: str,
    last_name: str,
    debug_steps: list[str] | None = None,
) -> dict[str, Any] | None:
    debug_steps = debug_steps if debug_steps is not None else []
    if not MEGAFON_VATS_WEBHOOK_URL or not first_name or not last_name:
        if not MEGAFON_VATS_WEBHOOK_URL:
            debug_steps.append("Megafon webhook URL не настроен (MEGAFON_VATS_WEBHOOK_URL пустой)")
        if not first_name or not last_name:
            debug_steps.append("Нельзя искать в Мегафоне: пустые имя или фамилия")
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
        debug_steps.append("Megafon webhook request завершился ошибкой")
        return None

    row = _find_employee_row(data, first_name, last_name)
    if row:
        debug_steps.append("Megafon: сотрудник найден по имени/фамилии")
    else:
        debug_steps.append("Megafon: сотрудник по имени/фамилии не найден")
    return row


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
