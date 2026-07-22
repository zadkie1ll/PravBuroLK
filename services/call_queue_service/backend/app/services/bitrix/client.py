from __future__ import annotations

from typing import Any

import requests

from ...config import settings


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

    def call_with_total(
        self,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        payload = _gateway_post(
            "call-with-total", {"profile": self.profile, "method": method, "params": params or {}}
        )
        return payload.get("items", []), payload.get("total", 0)

    def batch_call(
        self,
        commands: list[tuple[str, dict[str, Any] | None]],
    ) -> list[list[dict[str, Any]]]:
        if not commands:
            return []
        payload = _gateway_post(
            "batch-call",
            {
                "profile": self.profile,
                "commands": [{"method": method, "params": params} for method, params in commands],
            },
        )
        return payload.get("pages", [])

    def paginated_call(
        self,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        payload = _gateway_post(
            "paginated-call", {"profile": self.profile, "method": method, "params": params or {}}
        )
        return payload.get("items", [])
