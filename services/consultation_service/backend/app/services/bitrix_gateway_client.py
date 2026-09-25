from __future__ import annotations

from typing import Any

import httpx

from ..config import settings


class BitrixClient:
    """Тонкий клиент к bitrix_gateway_service — тот же паттерн, что
    services/documents_service/backend/app/services/bitrix_gateway_client.py.
    """

    def __init__(self, profile: str | None = None):
        self.profile = profile or settings.bitrix_gateway_profile

    def call(self, method: str, params: dict[str, Any] | None = None) -> Any:
        response = httpx.post(
            f"{settings.bitrix_gateway_base_url}/bitrix/call",
            json={"profile": self.profile, "method": method, "params": params or {}},
            headers={"Authorization": f"Bearer {settings.bitrix_gateway_token}"},
            timeout=30.0,
        )
        response.raise_for_status()
        payload = response.json()
        return payload.get("result")
