from __future__ import annotations

from typing import Any

import requests

from ..config import settings


class BitrixAPIError(Exception):
    pass


def _gateway_headers() -> dict[str, str]:
    if not settings.bitrix_gateway_token:
        return {}
    return {"Authorization": f"Bearer {settings.bitrix_gateway_token}"}


def _gateway_post(path: str, body: dict[str, Any]) -> dict[str, Any]:
    try:
        response = requests.post(
            f"{settings.bitrix_gateway_base_url}/bitrix/{path}",
            json=body,
            headers=_gateway_headers(),
            timeout=30,
        )
    except requests.RequestException as exc:
        raise BitrixAPIError(f"bitrix-gateway недоступен: {exc}") from exc
    if response.status_code >= 400:
        raise BitrixAPIError(f"bitrix-gateway error {response.status_code}: {response.text}")
    return response.json()


def call(method: str, params: dict[str, Any] | None = None) -> Any:
    payload = _gateway_post(
        "call",
        {"profile": settings.bitrix_gateway_profile, "method": method, "params": params or {}},
    )
    return payload.get("result")
