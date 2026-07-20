from __future__ import annotations

import time
from dataclasses import dataclass

import requests

from ..config import settings


@dataclass
class SalesManagerDTO:
    id: int
    name: str
    email: str
    is_active: bool
    megafon_user: str = ""
    megafon_group: str = ""
    megafon_clid: str = ""


class LeadreportClientError(Exception):
    pass


_cache: dict[str, tuple[float, object]] = {}


def _cache_get(key: str):
    entry = _cache.get(key)
    if not entry:
        return None
    expires_at, value = entry
    if time.monotonic() > expires_at:
        _cache.pop(key, None)
        return None
    return value


def _cache_set(key: str, value: object) -> None:
    _cache[key] = (time.monotonic() + settings.sales_manager_cache_ttl_seconds, value)


def get_by_email(email: str) -> SalesManagerDTO | None:
    cache_key = f"sales-manager:email:{email.lower()}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached or None

    try:
        response = requests.get(
            f"{settings.monolith_base_url}/api/internal/sales-managers/lookup/",
            params={"email": email},
            headers=_auth_headers(),
            timeout=10,
        )
    except requests.RequestException as exc:
        raise LeadreportClientError(f"Монолит недоступен: {exc}") from exc

    if response.status_code == 404:
        _cache_set(cache_key, None)
        return None
    response.raise_for_status()
    data = response.json()
    dto = SalesManagerDTO(
        id=data["id"],
        name=data["name"],
        email=data["email"],
        is_active=data["is_active"],
        megafon_user=data.get("megafon_user", ""),
        megafon_group=data.get("megafon_group", ""),
        megafon_clid=data.get("megafon_clid", ""),
    )
    _cache_set(cache_key, dto)
    return dto


def list_active() -> list[SalesManagerDTO]:
    cache_key = "sales-manager:list-active"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    try:
        response = requests.get(
            f"{settings.monolith_base_url}/api/internal/sales-managers/",
            headers=_auth_headers(),
            timeout=10,
        )
    except requests.RequestException as exc:
        raise LeadreportClientError(f"Монолит недоступен: {exc}") from exc

    response.raise_for_status()
    items = [
        SalesManagerDTO(
            id=item["id"],
            name=item["name"],
            email=item["email"],
            is_active=item["is_active"],
            megafon_user=item.get("megafon_user", ""),
            megafon_group=item.get("megafon_group", ""),
            megafon_clid=item.get("megafon_clid", ""),
        )
        for item in response.json()
    ]
    _cache_set(cache_key, items)
    return items


def _auth_headers() -> dict[str, str]:
    if not settings.monolith_internal_token:
        return {}
    return {"Authorization": f"Bearer {settings.monolith_internal_token}"}
