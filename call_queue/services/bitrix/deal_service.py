from __future__ import annotations

from datetime import datetime, time
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings

from call_queue.models import CallEntityType

from .client import BitrixClient
from ..phone_insights import build_phone_insights, normalize_russian_phone_digits


def _safe_int(value):
    if value in (None, "", "0", 0):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_phone(value: Any) -> str:
    return normalize_russian_phone_digits(str(value or ""), preserve_toll_free_8=True)


def _get_bitrix_timezone() -> ZoneInfo:
    timezone_name = getattr(settings, "CALL_QUEUE_BITRIX_TIME_ZONE", "Europe/Moscow")
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("Europe/Moscow")


def _build_bitrix_date_range(date_from, date_to) -> tuple[datetime, datetime]:
    bitrix_timezone = _get_bitrix_timezone()
    return (
        datetime.combine(date_from, time.min, tzinfo=bitrix_timezone),
        datetime.combine(date_to, time.max, tzinfo=bitrix_timezone),
    )


class BitrixDealService:
    deal_select_fields = [
        "ID",
        "TITLE",
        "CONTACT_ID",
        "STAGE_ID",
        "SOURCE_ID",
        "ASSIGNED_BY_ID",
        "DATE_CREATE",
        "PHONE",
        "NAME",
        "UF_*",
    ]
    lead_select_fields = [
        "ID",
        "TITLE",
        "CONTACT_ID",
        "STATUS_ID",
        "SOURCE_ID",
        "ASSIGNED_BY_ID",
        "DATE_CREATE",
        "PHONE",
        "NAME",
        "UF_*",
    ]
    production_deal_select_fields = [
        "ID",
        "TITLE",
        "CONTACT_ID",
        "STAGE_ID",
        "DATE_CREATE",
        "COMMENTS",
        "ASSIGNED_BY_ID",
    ]
    production_lead_select_fields = [
        "ID",
        "TITLE",
        "CONTACT_ID",
        "STATUS_ID",
        "DATE_CREATE",
        "COMMENTS",
        "ASSIGNED_BY_ID",
        "PHONE",
        "NAME",
        "LAST_NAME",
        "SECOND_NAME",
    ]

    def __init__(self, client: BitrixClient | None = None):
        self.client = client or BitrixClient()

    def get_stage_choices(self, entity_type: str = CallEntityType.DEAL) -> list[tuple[str, str]]:
        try:
            entity_id = "DEAL_STAGE" if entity_type == CallEntityType.DEAL else "STATUS"
            items = self.client.call("crm.status.list", {"filter": {"ENTITY_ID": entity_id}})
        except Exception:
            return []
        return [(item.get("STATUS_ID", ""), item.get("NAME", item.get("STATUS_ID", ""))) for item in items]

    def get_source_choices(self, entity_type: str = CallEntityType.DEAL) -> list[tuple[str, str]]:
        try:
            items = self.client.call("crm.status.list", {"filter": {"ENTITY_ID": "SOURCE"}})
        except Exception:
            return []
        return [(item.get("STATUS_ID", ""), item.get("NAME", item.get("STATUS_ID", ""))) for item in items]

    def get_responsible_choices(self) -> list[tuple[str, str]]:
        try:
            users = self.client.paginated_call(
                "user.get",
                {"filter": {"ACTIVE": True}, "select": ["ID", "NAME", "LAST_NAME"]},
            )
        except Exception:
            return []
        return [
            (
                str(user.get("ID", "")),
                " ".join(filter(None, [user.get("NAME"), user.get("LAST_NAME")])).strip()
                or str(user.get("ID", "")),
            )
            for user in users
        ]

    def fetch_deals(self, filters: dict[str, Any]) -> list[dict[str, Any]]:
        entity_type = filters.get("entity_type", CallEntityType.DEAL)
        date_from = datetime.fromisoformat(filters["date_from"]).date()
        date_to = datetime.fromisoformat(filters["date_to"]).date()
        from_dt, to_dt = _build_bitrix_date_range(date_from, date_to)

        bitrix_filter: dict[str, Any] = {
            ">=DATE_CREATE": from_dt.isoformat(),
            "<=DATE_CREATE": to_dt.isoformat(),
            "!PHONE": None,
        }
        stage_field = "STAGE_ID" if entity_type == CallEntityType.DEAL else "STATUS_ID"
        if filters.get("stage_id"):
            bitrix_filter[stage_field] = filters["stage_id"]
        elif filters.get("only_unanswered"):
            default_stage = (
                getattr(settings, "CALL_QUEUE_BITRIX_DEAL_UNANSWERED_STAGE_ID", "PREPARATION")
                if entity_type == CallEntityType.DEAL
                else getattr(settings, "CALL_QUEUE_BITRIX_LEAD_UNANSWERED_STATUS_ID", "IN_PROCESS")
            )
            bitrix_filter[stage_field] = default_stage
        if filters.get("source_id"):
            bitrix_filter["SOURCE_ID"] = filters["source_id"]
        if filters.get("responsible_id"):
            bitrix_filter["ASSIGNED_BY_ID"] = filters["responsible_id"]

        method = "crm.deal.list" if entity_type == CallEntityType.DEAL else "crm.lead.list"
        select_fields = self.deal_select_fields if entity_type == CallEntityType.DEAL else self.lead_select_fields
        entities = self.client.paginated_call(
            method,
            {
                "filter": bitrix_filter,
                "select": select_fields,
                "order": {"DATE_CREATE": "ASC", "ID": "ASC"},
            },
        )
        normalized = [self.normalize_entity(entity, entity_type) for entity in entities]
        if filters.get("only_without_repeat"):
            normalized = [deal for deal in normalized if not deal.get("repeat_unanswered")]
        return normalized

    def fetch_production_recall_deals(
        self,
        *,
        entity_type: str = CallEntityType.DEAL,
        date_from,
        date_to,
        stage_id: str = "PREPARATION",
    ) -> list[dict[str, Any]]:
        from_dt, to_dt = _build_bitrix_date_range(date_from, date_to)
        method = "crm.deal.list" if entity_type == CallEntityType.DEAL else "crm.lead.list"
        stage_field = "STAGE_ID" if entity_type == CallEntityType.DEAL else "STATUS_ID"
        select_fields = (
            self.production_deal_select_fields
            if entity_type == CallEntityType.DEAL
            else self.production_lead_select_fields
        )
        bitrix_filter = {
            ">=DATE_CREATE": from_dt.isoformat(),
            "<=DATE_CREATE": to_dt.isoformat(),
        }
        if stage_id:
            bitrix_filter[stage_field] = stage_id
        entities = self.client.paginated_call(
            method,
            {
                "filter": bitrix_filter,
                "select": select_fields,
                "order": {"DATE_CREATE": "ASC", "ID": "ASC"},
            },
        )
        return self._entities_to_recall_items(entities, entity_type, stage_field)

    def _entities_to_recall_items(
        self,
        entities: list[dict[str, Any]],
        entity_type: str,
        stage_field: str,
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for entity in entities:
            contact_id = _safe_int(entity.get("CONTACT_ID"))
            contact: dict[str, Any] = {}
            phones: list[str] = []
            raw_phones: list[str] = []
            if contact_id:
                contact = self.get_contact(contact_id)
                phones = self.extract_contact_phones(contact)
                raw_phones = self.extract_contact_raw_phones(contact)
            if not phones:
                phones = self.extract_entity_phones(entity)
                raw_phones = self.extract_entity_raw_phones(entity)
            if not phones:
                continue
            entity_id = _safe_int(entity.get("ID"))
            client_name = self.extract_contact_name(contact) or self.extract_entity_name(entity)
            items.append(
                {
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "deal_id": entity_id if entity_type == CallEntityType.DEAL else None,
                    "lead_id": entity_id if entity_type == CallEntityType.LEAD else None,
                    "contact_id": contact_id,
                    "client_name": client_name,
                    "phone": phones[0],
                    "raw_phone": raw_phones[0] if raw_phones else phones[0],
                    "phones": phones,
                    "bitrix_url": self.build_entity_url(entity_type, entity_id),
                    "comments": (entity.get("COMMENTS") or "").strip(),
                    "stage_id": str(entity.get(stage_field) or ""),
                    "created_at": entity.get("DATE_CREATE") or "",
                    "phone_insights": build_phone_insights(phones[0]),
                }
            )
        return items

    def search_production_entities(
        self,
        *,
        entity_type: str = CallEntityType.DEAL,
        query: str,
    ) -> list[dict[str, Any]]:
        query = (query or "").strip()
        if not query:
            return []
        stage_field = "STAGE_ID" if entity_type == CallEntityType.DEAL else "STATUS_ID"
        select_fields = (
            self.production_deal_select_fields
            if entity_type == CallEntityType.DEAL
            else self.production_lead_select_fields
        )
        method = "crm.deal.list" if entity_type == CallEntityType.DEAL else "crm.lead.list"
        digit_count = sum(char.isdigit() for char in query)

        if digit_count >= 7:
            normalized_phone = _normalize_phone(query)
            if not normalized_phone:
                return []
            duplicates = self.client.call(
                "crm.duplicate.findbycomm",
                {"type": "PHONE", "values": [normalized_phone]},
            ) or {}
            key = "DEAL" if entity_type == CallEntityType.DEAL else "LEAD"
            entity_ids = [_safe_int(entity_id) for entity_id in duplicates.get(key, [])]
            entity_ids = [entity_id for entity_id in entity_ids if entity_id]
            if not entity_ids:
                return []
            entities = self.client.paginated_call(
                method,
                {
                    "filter": {"ID": entity_ids},
                    "select": select_fields,
                    "order": {"DATE_CREATE": "ASC", "ID": "ASC"},
                },
            )
        else:
            entities = self.client.paginated_call(
                method,
                {
                    "filter": {"%TITLE": query},
                    "select": select_fields,
                    "order": {"DATE_CREATE": "ASC", "ID": "ASC"},
                },
            )
        return self._entities_to_recall_items(entities, entity_type, stage_field)

    def get_contact(self, contact_id: int) -> dict[str, Any]:
        return self.client.call("crm.contact.get", {"id": int(contact_id)})

    def get_deal(self, deal_id: int) -> dict[str, Any]:
        return self.client.call("crm.deal.get", {"id": int(deal_id)})

    def get_lead(self, lead_id: int) -> dict[str, Any]:
        return self.client.call("crm.lead.get", {"id": int(lead_id)})

    def extract_contact_phones(self, contact: dict[str, Any]) -> list[str]:
        raw_phone = contact.get("PHONE") or []
        if not isinstance(raw_phone, list):
            return []
        prioritized = []
        for entry in raw_phone:
            value = _normalize_phone((entry or {}).get("VALUE") or "")
            if value:
                value_type = str((entry or {}).get("VALUE_TYPE") or "").upper()
                priority = {
                    "MOBILE": 0,
                    "WORK": 1,
                    "OTHER": 2,
                    "HOME": 3,
                    "FAX": 4,
                }.get(value_type, 9)
                prioritized.append((priority, value))
        prioritized.sort(key=lambda item: item[0])
        return [value for _, value in prioritized]

    def extract_contact_raw_phones(self, contact: dict[str, Any]) -> list[str]:
        raw_phone = contact.get("PHONE") or []
        if not isinstance(raw_phone, list):
            return []
        phones = []
        for entry in raw_phone:
            value = str((entry or {}).get("VALUE") or "").strip()
            if value:
                phones.append(value)
        return phones

    def extract_contact_name(self, contact: dict[str, Any]) -> str:
        name_parts = [
            str(contact.get("NAME") or "").strip(),
            str(contact.get("SECOND_NAME") or "").strip(),
            str(contact.get("LAST_NAME") or "").strip(),
        ]
        return " ".join(part for part in name_parts if part).strip()

    def extract_entity_name(self, entity: dict[str, Any]) -> str:
        name_parts = [
            str(entity.get("NAME") or "").strip(),
            str(entity.get("SECOND_NAME") or "").strip(),
            str(entity.get("LAST_NAME") or "").strip(),
        ]
        full_name = " ".join(part for part in name_parts if part).strip()
        return full_name or str(entity.get("TITLE") or "").strip()

    def extract_entity_phones(self, entity: dict[str, Any]) -> list[str]:
        raw_phone = entity.get("PHONE") or []
        if not isinstance(raw_phone, list):
            return []
        phones = []
        for entry in raw_phone:
            value = _normalize_phone((entry or {}).get("VALUE") or "")
            if value:
                phones.append(value)
        return phones

    def extract_entity_raw_phones(self, entity: dict[str, Any]) -> list[str]:
        raw_phone = entity.get("PHONE") or []
        if not isinstance(raw_phone, list):
            return []
        phones = []
        for entry in raw_phone:
            value = str((entry or {}).get("VALUE") or "").strip()
            if value:
                phones.append(value)
        return phones

    def append_deal_comment(self, deal_id: int, line: str) -> str:
        deal = self.get_deal(deal_id)
        current_comments = str(deal.get("COMMENTS") or "").strip()
        new_comments = f"{current_comments}\n{line}".strip() if current_comments else line
        self.client.call(
            "crm.deal.update",
            {
                "id": int(deal_id),
                "fields": {
                    "COMMENTS": new_comments,
                },
            },
        )
        return new_comments

    def append_entity_comment(self, entity_type: str, entity_id: int, line: str) -> str:
        if entity_type == CallEntityType.LEAD:
            entity = self.get_lead(entity_id)
            current_comments = str(entity.get("COMMENTS") or "").strip()
            new_comments = f"{current_comments}\n{line}".strip() if current_comments else line
            self.client.call(
                "crm.lead.update",
                {
                    "id": int(entity_id),
                    "fields": {
                        "COMMENTS": new_comments,
                    },
                },
            )
            return new_comments
        return self.append_deal_comment(entity_id, line)

    def normalize_entity(self, entity: dict[str, Any], entity_type: str) -> dict[str, Any]:
        raw_phone = entity.get("PHONE")
        if isinstance(raw_phone, list):
            phone = (raw_phone[0] or {}).get("VALUE", "") if raw_phone else ""
        else:
            phone = raw_phone or ""

        created_at = entity.get("DATE_CREATE")
        if created_at:
            try:
                created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            except ValueError:
                created_at = None

        stage_field = "STAGE_ID" if entity_type == CallEntityType.DEAL else "STATUS_ID"
        entity_id = _safe_int(entity.get("ID"))
        return {
            "entity_type": entity_type,
            "bitrix_entity_id": entity_id,
            "bitrix_contact_id": _safe_int(entity.get("CONTACT_ID")),
            "client_name": (entity.get("NAME") or entity.get("TITLE") or "").strip(),
            "phone": phone,
            "lead_created_at": created_at,
            "source_id": str(entity.get("SOURCE_ID") or ""),
            "source_name": str(entity.get("SOURCE_ID") or ""),
            "stage_id": str(entity.get(stage_field) or ""),
            "stage_name": str(entity.get(stage_field) or ""),
            "responsible_id": str(entity.get("ASSIGNED_BY_ID") or ""),
            "responsible_name": str(entity.get("ASSIGNED_BY_ID") or ""),
            "bitrix_url": self.build_entity_url(entity_type, entity_id),
            "last_call_result": self.extract_last_call_result(entity),
            "repeat_unanswered": self.extract_repeat_unanswered(entity),
        }

    def update_entity_after_call(self, entity_type: str, entity_id: int, result: str, repeat_unanswered: bool):
        fields: dict[str, Any] = {}
        last_call_field = getattr(settings, "BITRIX_DEAL_LAST_CALL_RESULT_FIELD", "")
        repeat_field = getattr(settings, "BITRIX_DEAL_REPEAT_UNANSWERED_FIELD", "")
        if last_call_field:
            fields[last_call_field] = result
        if repeat_field:
            fields[repeat_field] = "1" if repeat_unanswered else "0"
        if not fields:
            return {"skipped": True}
        method = "crm.deal.update" if entity_type == CallEntityType.DEAL else "crm.lead.update"
        return self.client.call(method, {"id": int(entity_id), "fields": fields})

    def build_entity_url(self, entity_type: str, entity_id: int | None) -> str:
        if not entity_id:
            return ""
        base_url = getattr(settings, "BITRIX_BASE_URL", "").rstrip("/")
        if not base_url:
            webhook = getattr(settings, "BITRIX_WEBHOOK_URL", "")
            if "/rest/" in webhook:
                base_url = webhook.split("/rest/")[0].rstrip("/")
        if not base_url:
            return ""
        path = "deal" if entity_type == CallEntityType.DEAL else "lead"
        return f"{base_url}/crm/{path}/details/{entity_id}/"

    def extract_last_call_result(self, deal: dict[str, Any]) -> str:
        field_name = getattr(settings, "BITRIX_DEAL_LAST_CALL_RESULT_FIELD", "")
        return str(deal.get(field_name) or "") if field_name else ""

    def extract_repeat_unanswered(self, deal: dict[str, Any]) -> bool:
        field_name = getattr(settings, "BITRIX_DEAL_REPEAT_UNANSWERED_FIELD", "")
        if not field_name:
            return False
        return str(deal.get(field_name) or "") in {"1", "Y", "y", "true", "True"}
