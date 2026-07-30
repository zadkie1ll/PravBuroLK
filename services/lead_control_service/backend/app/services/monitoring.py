"""Порт lead_control/services.py — вся логика повторных попыток дозвона и
периодических задач модератору."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone as dt_timezone

from sqlalchemy.orm import Session

from ..config import settings
from ..models import LeadMonitor, LeadMonitorStatus
from . import bitrix_lead_control as bitrix
from .bitrix_gateway_client import BitrixAPIError


def _now() -> datetime:
    return datetime.now(dt_timezone.utc)


def is_logic_disabled(deal_data: dict) -> bool:
    return str(deal_data.get(settings.lead_control_disable_field)) == "1"


def is_monitored_stage(stage_id: str) -> bool:
    return stage_id in settings.monitored_stages_set


def is_within_working_hours(now: datetime | None = None) -> bool:
    now = now or _now()
    return settings.lead_control_workday_start_hour <= now.hour < settings.lead_control_workday_end_hour


def get_end_of_today_deadline(now: datetime | None = None) -> str:
    now = now or _now()
    end_of_day = now.replace(hour=23, minute=59, second=0, microsecond=0)
    return end_of_day.isoformat(timespec="seconds")


def get_allowed_attempts_for_today(monitor: LeadMonitor, now: datetime | None = None) -> int:
    """
    Правила:
    - если лид поступил 10:00-13:00 -> 3 попытки в этот день
    - если 13:00-16:00 -> 2 попытки
    - если 16:00-19:00 -> 1 попытка
    - на следующий день и далее -> до 3 попыток в день
    """
    now = now or _now()

    if not monitor.entered_logic_at:
        return 0

    entered_at = monitor.entered_logic_at
    if entered_at.date() != now.date():
        return 3

    entered_float = entered_at.hour + entered_at.minute / 60

    if 10 <= entered_float < 13:
        return 3
    if 13 <= entered_float < 16:
        return 2
    if 16 <= entered_float < 19:
        return 1
    return 0


def can_create_next_attempt(monitor: LeadMonitor, now: datetime | None = None) -> bool:
    now = now or _now()

    if not is_within_working_hours(now):
        return False

    monitor.reset_daily_attempts_if_needed(now.date())

    allowed_attempts = get_allowed_attempts_for_today(monitor, now)
    return monitor.attempts_today < allowed_attempts


def mark_success(db: Session, monitor: LeadMonitor, comment: str) -> None:
    monitor.is_active = False
    monitor.status = LeadMonitorStatus.SUCCESS.value
    monitor.status_comment = comment
    monitor.last_checked_at = _now()
    db.commit()


def mark_skipped(db: Session, monitor: LeadMonitor, comment: str) -> None:
    monitor.is_active = False
    monitor.status = LeadMonitorStatus.SKIPPED.value
    monitor.status_comment = comment
    monitor.last_checked_at = _now()
    db.commit()


def mark_error(db: Session, monitor: LeadMonitor, comment: str) -> None:
    monitor.status = LeadMonitorStatus.ERROR.value
    monitor.status_comment = comment
    monitor.last_checked_at = _now()
    db.commit()


def create_and_bind_typical_task(db: Session, monitor: LeadMonitor, now: datetime | None = None) -> int:
    now = now or _now()

    task_id = bitrix.create_typical_task(
        deal_id=monitor.bitrix_deal_id,
        responsible_id=monitor.responsible_bitrix_user_id,
        auditor_id=monitor.moderator_bitrix_user_id,
        title=settings.lead_control_typical_task_title,
        description=settings.lead_control_typical_task_description,
        deadline=get_end_of_today_deadline(now),
    )

    monitor.bitrix_task_id = task_id
    monitor.attempts_total += 1
    monitor.attempts_today += 1
    monitor.status = LeadMonitorStatus.ACTIVE.value
    monitor.status_comment = ""
    monitor.last_checked_at = _now()
    db.commit()

    return task_id


def should_create_moderator_task(monitor: LeadMonitor, now: datetime | None = None) -> bool:
    now = now or _now()
    interval_days = timedelta(days=settings.lead_control_moderator_task_every_days)

    if not monitor.moderator_bitrix_user_id:
        return False

    if not monitor.last_moderator_task_created_at:
        if not monitor.entered_logic_at:
            return False
        return now >= monitor.entered_logic_at + interval_days

    return now >= monitor.last_moderator_task_created_at + interval_days


def resolve_moderator_task_deal_id(monitor: LeadMonitor, deal_data: dict | None = None) -> int:
    deal_data = deal_data or {}
    contact_id = deal_data.get("CONTACT_ID")
    try:
        contact_id = int(contact_id)
    except (TypeError, ValueError):
        return monitor.bitrix_deal_id

    sales_deals = bitrix.find_deals_by_contact_and_category(
        contact_id,
        settings.lead_control_sales_deal_category_id,
        exclude_deal_id=monitor.bitrix_deal_id,
    )
    if not sales_deals:
        return monitor.bitrix_deal_id

    sales_deal_id = sales_deals[0].get("ID")
    try:
        return int(sales_deal_id)
    except (TypeError, ValueError):
        return monitor.bitrix_deal_id


def create_periodic_moderator_task(
    db: Session, monitor: LeadMonitor, deal_data: dict | None = None, now: datetime | None = None
) -> int:
    now = now or _now()
    deal_id = resolve_moderator_task_deal_id(monitor, deal_data)

    task_id = bitrix.create_typical_task(
        deal_id=deal_id,
        responsible_id=monitor.moderator_bitrix_user_id,
        created_by_id=settings.lead_control_moderator_task_creator_id,
        title=settings.lead_control_moderator_task_title,
        description=settings.lead_control_moderator_task_description,
        deadline=get_end_of_today_deadline(now),
    )

    monitor.last_moderator_task_id = task_id
    monitor.last_moderator_task_created_at = _now()
    monitor.last_checked_at = _now()
    db.commit()

    return task_id


def process_monitor(db: Session, monitor: LeadMonitor) -> dict:
    """
    Возвращает словарь:
    - result: основной результат обработки
    - moderator_task_created: была ли создана периодическая задача модератору
    """
    now = _now()
    moderator_task_created = False

    try:
        monitor.reset_daily_attempts_if_needed(now.date())
        db.commit()

        deal_data = bitrix.get_deal_by_id(monitor.bitrix_deal_id)
        stage_id = (deal_data.get("STAGE_ID") or "").strip()

        monitor.current_stage_id = stage_id
        monitor.raw_deal_data = deal_data
        monitor.last_checked_at = _now()
        db.commit()

        if is_logic_disabled(deal_data):
            mark_skipped(db, monitor, "Логика отключена полем в сделке")
            return {"result": "skipped", "moderator_task_created": moderator_task_created}

        if not is_monitored_stage(stage_id):
            mark_success(db, monitor, "Сделка ушла со стадии мониторинга")
            return {"result": "success", "moderator_task_created": moderator_task_created}

        if should_create_moderator_task(monitor, now):
            create_periodic_moderator_task(db, monitor, deal_data, now)
            moderator_task_created = True

        if not monitor.responsible_bitrix_user_id:
            mark_error(db, monitor, "Не заполнен responsible_bitrix_user_id")
            return {"result": "error", "moderator_task_created": moderator_task_created}

        if not monitor.bitrix_task_id:
            if not can_create_next_attempt(monitor, now):
                db.commit()
                return {"result": "waiting_time", "moderator_task_created": moderator_task_created}

            create_and_bind_typical_task(db, monitor, now)
            return {"result": "task_created", "moderator_task_created": moderator_task_created}

        task_data = bitrix.get_task_by_id(monitor.bitrix_task_id)

        if not bitrix.is_task_completed(task_data):
            return {"result": "waiting_task", "moderator_task_created": moderator_task_created}

        monitor.last_task_closed_at = _now()
        db.commit()

        if not can_create_next_attempt(monitor, now):
            db.commit()
            return {"result": "waiting_time", "moderator_task_created": moderator_task_created}

        create_and_bind_typical_task(db, monitor, now)
        return {"result": "task_created", "moderator_task_created": moderator_task_created}

    except BitrixAPIError as exc:
        mark_error(db, monitor, f"Bitrix API error: {exc}")
        return {"result": "error", "moderator_task_created": moderator_task_created}
    except Exception as exc:
        mark_error(db, monitor, f"Unexpected error: {exc}")
        return {"result": "error", "moderator_task_created": moderator_task_created}


def process_all_active_monitors(db: Session) -> dict:
    stats = {
        "total": 0,
        "success": 0,
        "skipped": 0,
        "waiting_task": 0,
        "waiting_time": 0,
        "task_created": 0,
        "moderator_task_created": 0,
        "error": 0,
    }

    monitors = db.query(LeadMonitor).filter(LeadMonitor.is_active.is_(True)).order_by(LeadMonitor.id).all()

    for monitor in monitors:
        stats["total"] += 1
        result_payload = process_monitor(db, monitor)
        result = result_payload.get("result")
        if result in stats:
            stats[result] += 1
        if result_payload.get("moderator_task_created"):
            stats["moderator_task_created"] += 1

    return stats
