from __future__ import annotations

from typing import Any

import requests
from django.conf import settings


class BitrixAPIError(Exception):
    pass


class BitrixClient:
    def __init__(self, webhook_url: str | None = None):
        self.webhook_url = (webhook_url or settings.BITRIX_WEBHOOK_URL).rstrip("/")

    def call(self, method: str, params: dict[str, Any] | None = None) -> Any:
        response = requests.post(
            f"{self.webhook_url}/{method}.json",
            json=params or {},
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
        if "error" in payload:
            raise BitrixAPIError(
                f"{payload['error']}: {payload.get('error_description', 'Bitrix API error')}"
            )
        return payload.get("result")

    def paginated_call(
        self,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        params = params or {}
        collected: list[dict[str, Any]] = []
        start = 0
        while True:
            result = self.call(method, {**params, "start": start})
            page_items = result if isinstance(result, list) else result.get("items", [])
            if not page_items:
                break
            collected.extend(page_items)
            if len(page_items) < 50:
                break
            start += 50
        return collected
