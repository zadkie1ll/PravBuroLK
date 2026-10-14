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


def process_contact(call: Callable, contact_id: str, field_code: str, dry_run: bool) -> tuple[str, int]:
    try:
        result = call("crm.contact.get", {"id": int(contact_id)})
        contact = result if isinstance(result, dict) else None
        if not contact:
            raise ProcessingError("INVALID_CONTACT_RESPONSE", True)
        phones = contact.get("PHONE") or []
        if isinstance(phones, dict):
            phones = list(phones.values())
        if not isinstance(phones, list):
            raise ProcessingError("INVALID_CONTACT_PHONE", True)
        value = next((phone.get("VALUE") for phone in phones if isinstance(phone, dict) and phone.get("VALUE")), None)
        if not value:
            raise ProcessingError("CONTACT_PHONE_NOT_READY", True)
        if contact.get(field_code):
            return "already_filled", 0
        if not dry_run:
            call("crm.contact.update", {"id": int(contact_id), "fields": {field_code: value}})
        return ("dry_run" if dry_run else "done"), 1
    except BitrixAPIError as exc:
        raise ProcessingError("BITRIX_REQUEST_FAILED", exc.retryable) from None


def process_converted_lead(call: Callable, lead_id: str, stage_id: str,
                           field_code: str, dry_run: bool) -> tuple[str, int]:
    try:
        result = call("crm.lead.get", {"id": int(lead_id)})
        lead = result if isinstance(result, dict) else None
        if not lead:
            raise ProcessingError("INVALID_LEAD_RESPONSE", True)
        if str(lead.get("STATUS_ID", "")) != stage_id:
            return "filtered", 0
        contact_id = str(lead.get("CONTACT_ID") or "")
        if not re.fullmatch(r"[1-9][0-9]*", contact_id):
            raise ProcessingError("CONTACT_NOT_READY", True)
        return process_contact(call, contact_id, field_code, dry_run)
    except BitrixAPIError as exc:
        raise ProcessingError("BITRIX_REQUEST_FAILED", exc.retryable) from None
