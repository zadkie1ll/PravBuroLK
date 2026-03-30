from __future__ import annotations

from datetime import datetime, time
from typing import Any

from django.conf import settings
from django.utils import timezone

from call_queue.models import CallEntityType

from .client import BitrixClient


def _safe_int(value):
    if value in (None, "", "0", 0):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


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
        from_dt = timezone.make_aware(datetime.combine(date_from, time.min))
        to_dt = timezone.make_aware(datetime.combine(date_to, time.max))

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
