from __future__ import annotations

from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import BitrixSyncLog

MEGAFON_FINAL_STATUS_LABELS = {
    "Success": ("connected", "Соединение установлено, клиент не подтверждён"),
    "Busy": ("unreachable", "Не дозвонились: занято"),
    "NotAvailable": ("unreachable", "Номер недоступен или набран неверно"),
    "missed": ("unreachable", "Не дозвонились: не взял трубку"),
}

MEGAFON_EVENT_TITLES = {
    ("OUTGOING", "out"): "Набираем номер клиента",
    ("OUTGOING", ""): "Исходящий звонок",
    ("INCOMING", "in"): "Входящий звонок менеджеру",
    ("INCOMING", ""): "Входящий звонок",
    ("ACCEPTED", "in"): "Менеджер снял трубку",
    ("ACCEPTED", "out"): "Клиент снял трубку",
    ("ACCEPTED", ""): "Трубку сняли",
    ("COMPLETED", "out"): "Разговор завершён",
    ("COMPLETED", "in"): "Разговор завершён",
    ("COMPLETED", ""): "Разговор завершён",
    ("CANCELLED", "in"): "Сброс на стороне менеджера",
    ("CANCELLED", "out"): "Клиент сбросил или не дождался",
    ("CANCELLED", ""): "Звонок отменён",
}

MEGAFON_HISTORY_TITLES = {
    "Success": "Итог: разговор состоялся",
    "Busy": "Итог: занято или сброс",
    "NotAvailable": "Итог: номер недоступен",
    "missed": "Итог: не взяли трубку",
}


def humanize_megafon_log(cmd: str, event_type: str, status: str, direction: str) -> str:
    if cmd == "history":
        return MEGAFON_HISTORY_TITLES.get(status, f"Итог звонка: {status or 'неизвестно'}")
    if cmd == "event":
        title = MEGAFON_EVENT_TITLES.get((event_type, direction))
        if title:
            return title
        return MEGAFON_EVENT_TITLES.get((event_type, ""), f"Событие: {event_type or 'неизвестно'}")
    return ""


def serialize_megafon_log(log: BitrixSyncLog) -> dict:
    payload = log.request_payload.get("payload", {}) if isinstance(log.request_payload, dict) else {}
    cmd = payload.get("cmd", "")
    event_type = payload.get("type", "")
    status = payload.get("status", "")
    direction = payload.get("direction", "")
    if cmd == "history":
        title = f"history: {status or 'unknown'}"
    elif cmd == "event":
        title = f"event: {event_type or 'unknown'}"
    elif cmd:
        title = f"{cmd}: {event_type or status or 'received'}"
    else:
        title = "callback"

    try:
        local_created_at = log.created_at.astimezone(ZoneInfo(settings.call_queue_bitrix_time_zone))
    except Exception:
        local_created_at = log.created_at

    return {
        "created_at": local_created_at.isoformat(),
        "title": title,
        "title_human": humanize_megafon_log(cmd, event_type, status, direction) or title,
        "cmd": cmd,
        "type": event_type,
        "status": status,
        "direction": direction,
        "payload": payload,
    }


def build_megafon_phone_result(snapshot: dict) -> dict:
    history_status = snapshot.get("latest_history_status")
    if history_status == "Success":
        return {"state": "connected", "label": "Соединение есть, но клиент не подтверждён"}
    if history_status == "missed":
        return {"state": "unanswered", "label": "Не взял трубку"}
    if history_status == "Busy":
        return {"state": "unanswered", "label": "Клиент сбросил или занято"}
    if history_status == "NotAvailable":
        return {"state": "invalid", "label": "Номер недоступен или набран неверно"}

    last_event_type = snapshot.get("last_event_type")
    last_event_direction = snapshot.get("last_event_direction")
    if last_event_type == "ACCEPTED":
        if last_event_direction == "out":
            return {"state": "connected", "label": "Есть ответ, но клиент не подтверждён"}
        if last_event_direction == "in":
            return {"state": "in_progress", "label": "Менеджер взял трубку"}
    if last_event_type == "CANCELLED":
        if last_event_direction == "in":
            return {"state": "cancelled", "label": "Сброс или отмена у менеджера"}
        if last_event_direction == "out":
            return {"state": "cancelled", "label": "Сброс или отмена у клиента"}
        return {"state": "cancelled", "label": "Сброс или отмена"}

    return {"state": "pending", "label": "Ожидаем результат"}


def build_megafon_call_snapshot(db: Session, call_id: str) -> dict:
    logs = list(
        db.execute(
            select(BitrixSyncLog)
            .where(
                BitrixSyncLog.entity_type == "megafon_webhook",
                BitrixSyncLog.entity_id == call_id,
                BitrixSyncLog.success == True,  # noqa: E712
            )
            .order_by(BitrixSyncLog.created_at, BitrixSyncLog.id)
        ).scalars()
    )
    timeline = [serialize_megafon_log(log) for log in logs]

    marker = {"state": "pending", "label": "Ожидаем события от МегаФона"}
    manager_answered = False
    latest_history_status = ""
    last_event_type = ""
    last_event_direction = ""

    for entry in timeline:
        if entry["cmd"] == "event" and entry["type"] == "ACCEPTED":
            manager_answered = True
        if entry["cmd"] == "event" and entry["type"]:
            last_event_type = entry["type"]
            last_event_direction = entry["direction"]
        if entry["cmd"] == "history" and entry["status"]:
            latest_history_status = entry["status"]

    if latest_history_status:
        state, label = MEGAFON_FINAL_STATUS_LABELS.get(
            latest_history_status,
            ("completed", f"Звонок завершен: {latest_history_status}"),
        )
        marker = {"state": state, "label": label}
    elif manager_answered:
        marker = {"state": "in_progress", "label": "Есть ответ по одной из ног звонка"}
    elif timeline:
        marker = {"state": "in_progress", "label": "Звонок в процессе"}

    phone_result = build_megafon_phone_result(
        {
            "latest_history_status": latest_history_status,
            "last_event_type": last_event_type,
            "last_event_direction": last_event_direction,
        }
    )

    return {
        "call_id": call_id,
        "marker": marker,
        "manager_answered": manager_answered,
        "latest_history_status": latest_history_status,
        "last_event_type": last_event_type,
        "last_event_direction": last_event_direction,
        "phone_result": phone_result,
        "requires_manager_confirmation": phone_result["state"] == "connected",
        "timeline": timeline[-20:],
    }
