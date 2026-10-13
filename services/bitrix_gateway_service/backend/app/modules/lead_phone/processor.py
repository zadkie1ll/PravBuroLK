from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable

from ...services.client import BitrixAPIError


class ProcessingError(Exception):
    def __init__(self, code: str, retryable: bool = False):
        super().__init__(code)
        self.code = code
        self.retryable = retryable


@dataclass(frozen=True)
class Options:
    from_type: str = "OTHER"
    to_type: str = "WORK"
    allowed_sources: frozenset[str] = frozenset()
    dry_run: bool = True
    max_attempts: int = 8
    retry_seconds: float = 2

    def validate(self):
        types = {"WORK", "MOBILE", "HOME", "FAX", "PAGER", "OTHER"}
        if self.from_type not in types or self.to_type not in types or self.from_type == self.to_type:
            raise ValueError("invalid_phone_types")


def extract_id(body: Any) -> str | None:
    if not isinstance(body, dict):
        return None
    value = body.get("data[FIELDS][ID]")
    if value is None:
        data = body.get("data")
        fields = data.get("FIELDS") if isinstance(data, dict) else None
        value = fields.get("ID") if isinstance(fields, dict) else None
    text = str(value)
    if not re.fullmatch(r"[1-9][0-9]{0,18}", text) or int(text) > 2**63 - 1:
        return None
    return text


def phone_changes(item: dict, options: Options) -> dict[str, dict]:
    raw_fields = item.get("fm") or {}
    # crm.item.get returns fm as an object keyed by the existing multifield ID.
    # Accept a list too for compatibility with wrappers that normalize the response.
    if isinstance(raw_fields, dict):
        fields = [{**field, "id": key} for key, field in raw_fields.items() if isinstance(field, dict)]
        if len(fields) != len(raw_fields):
            raise ProcessingError("INVALID_MULTIFIELDS")
    elif isinstance(raw_fields, list) and all(isinstance(field, dict) for field in raw_fields):
        fields = raw_fields
    else:
        raise ProcessingError("INVALID_MULTIFIELDS")
    changes = {}
    for field in fields:
        if field.get("typeId") != "PHONE" or field.get("valueType") != options.from_type:
            continue
        record_id, value = str(field.get("id")), field.get("value")
        if not re.fullmatch(r"[1-9][0-9]*", record_id) or not isinstance(value, str) or not value.strip():
            raise ProcessingError("INVALID_PHONE_RECORD")
        changes[record_id] = {"typeId": "PHONE", "valueType": options.to_type, "value": value}
    return changes


def process_lead(call: Callable, lead_id: str, options: Options) -> tuple[str, int]:
    try:
        result = call("crm.item.get", {"entityTypeId": 1, "id": int(lead_id)})
        item = result.get("item") if isinstance(result, dict) else None
        if not isinstance(item, dict):
            raise ProcessingError("INVALID_ITEM_RESPONSE", True)
        if options.allowed_sources and str(item.get("sourceId", "")) not in options.allowed_sources:
            return "filtered", 0
        changes = phone_changes(item, options)
        raw_fields = item.get("fm") or {}
        fields = list(raw_fields.values()) if isinstance(raw_fields, dict) else raw_fields
        if not any(isinstance(field, dict) and field.get("typeId") == "PHONE" for field in fields):
            raise ProcessingError("PHONE_NOT_READY", True)
        if changes and not options.dry_run:
            # Numeric keys modify existing records; n0/n1 would create duplicates.
            call("crm.item.update", {"entityTypeId": 1, "id": int(lead_id), "fields": {"fm": changes}})
        return ("dry_run" if options.dry_run else "done"), len(changes)
    except BitrixAPIError as exc:
        # Never log str(exc): it can contain phone numbers or webhook URLs.
        raise ProcessingError("BITRIX_REQUEST_FAILED", exc.retryable) from None
