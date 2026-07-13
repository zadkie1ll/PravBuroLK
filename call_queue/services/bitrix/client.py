from __future__ import annotations

from typing import Any
from urllib.parse import quote

import requests
from django.conf import settings

BITRIX_PAGE_SIZE = 50
BITRIX_BATCH_LIMIT = 50


class BitrixAPIError(Exception):
    pass


def _encode_bitrix_query(params: Any, prefix: str = "") -> list[str]:
    parts: list[str] = []
    if isinstance(params, dict):
        for key, value in params.items():
            key_part = quote(str(key), safe="")
            new_prefix = f"{prefix}%5B{key_part}%5D" if prefix else key_part
            parts.extend(_encode_bitrix_query(value, new_prefix))
    elif isinstance(params, (list, tuple)):
        for index, value in enumerate(params):
            new_prefix = f"{prefix}%5B{index}%5D"
            parts.extend(_encode_bitrix_query(value, new_prefix))
    else:
        parts.append(f"{prefix}={quote(str(params), safe='')}")
    return parts


def _build_batch_command(method: str, params: dict[str, Any] | None) -> str:
    query_string = "&".join(_encode_bitrix_query(params or {}))
    return f"{method}?{query_string}" if query_string else method


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

    def call_with_total(
        self,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
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
        result = payload.get("result")
        items = result if isinstance(result, list) else (result or {}).get("items", [])
        total = payload.get("total")
        return items, total if isinstance(total, int) else len(items)

    def batch_call(
        self,
        commands: list[tuple[str, dict[str, Any] | None]],
    ) -> list[list[dict[str, Any]]]:
        if not commands:
            return []
        cmd_map = {
            f"cmd{index}": _build_batch_command(method, params)
            for index, (method, params) in enumerate(commands)
        }
        response = requests.post(
            f"{self.webhook_url}/batch.json",
            json={"halt": 0, "cmd": cmd_map},
            timeout=90,
        )
        response.raise_for_status()
        payload = response.json()
        if "error" in payload:
            raise BitrixAPIError(
                f"{payload['error']}: {payload.get('error_description', 'Bitrix API error')}"
            )
        results_by_cmd = (payload.get("result") or {}).get("result") or {}
        ordered_results: list[list[dict[str, Any]]] = []
        for index in range(len(commands)):
            page_items = results_by_cmd.get(f"cmd{index}", [])
            ordered_results.append(page_items if isinstance(page_items, list) else [])
        return ordered_results

    def paginated_call(
        self,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        params = params or {}
        first_page, total = self.call_with_total(method, {**params, "start": 0})
        collected: list[dict[str, Any]] = list(first_page)
        if len(first_page) < BITRIX_PAGE_SIZE or total <= len(collected):
            return collected

        remaining_starts = list(range(BITRIX_PAGE_SIZE, total, BITRIX_PAGE_SIZE))
        for chunk_start in range(0, len(remaining_starts), BITRIX_BATCH_LIMIT):
            chunk_starts = remaining_starts[chunk_start : chunk_start + BITRIX_BATCH_LIMIT]
            commands = [(method, {**params, "start": start}) for start in chunk_starts]
            for page_items in self.batch_call(commands):
                if page_items:
                    collected.extend(page_items)
        return collected
