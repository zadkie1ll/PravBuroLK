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
            timeout=90,
        )
    except requests.RequestException as exc:
        raise BitrixAPIError(f"bitrix-gateway недоступен: {exc}") from exc
    if response.status_code >= 400:
        raise BitrixAPIError(f"bitrix-gateway error {response.status_code}: {response.text}")
    return response.json()


class BitrixClient:
    def __init__(self, profile: str | None = None):
        self.profile = profile or settings.bitrix_gateway_profile

    def call(self, method: str, params: dict[str, Any] | None = None) -> Any:
        payload = _gateway_post(
            "call", {"profile": self.profile, "method": method, "params": params or {}}
        )
        return payload.get("result")

    def paginated_call(self, method: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        payload = _gateway_post(
            "paginated-call", {"profile": self.profile, "method": method, "params": params or {}}
        )
        return payload.get("items", [])
