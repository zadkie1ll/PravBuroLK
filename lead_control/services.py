from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .bitrix_api import (
    BitrixAPIError,
    create_typical_task,
    find_deals_by_contact_and_category,
    get_deal_by_id,
    get_task_by_id,
    is_task_completed,
)
from .models import LeadMonitor, LeadMonitorStatus


def get_disable_field_code() -> str:
    return settings.LEAD_CONTROL_DISABLE_FIELD


def get_monitored_stages() -> set[str]:
    return set(getattr(settings, "LEAD_CONTROL_MONITORED_STAGES", []))


def get_typical_task_title() -> str:
    return getattr(settings, "LEAD_CONTROL_TYPICAL_TASK_TITLE", "Связаться с клиентом")


def get_typical_task_description() -> str:
    return getattr(
        settings,
        "LEAD_CONTROL_TYPICAL_TASK_DESCRIPTION",
        "Необходимо повторно связаться с клиентом по сделке."
    )


def get_moderator_task_title() -> str:
    return getattr(settings, "LEAD_CONTROL_MODERATOR_TASK_TITLE", "Проверить ситуацию клиента")


def get_moderator_task_description() -> str:
    return getattr(
        settings,
        "LEAD_CONTROL_MODERATOR_TASK_DESCRIPTION",
        "Проверить текущую ситуацию клиента по сделке."
    )


def get_moderator_task_creator_id() -> int:
    return int(getattr(settings, "LEAD_CONTROL_MODERATOR_TASK_CREATOR_ID", 444))


def get_moderator_task_interval_days() -> int:
    return int(getattr(settings, "LEAD_CONTROL_MODERATOR_TASK_EVERY_DAYS", 3))


def get_sales_deal_category_id() -> int:
    return int(getattr(settings, "LEAD_CONTROL_SALES_DEAL_CATEGORY_ID", 2))


def is_logic_disabled(deal_data: dict) -> bool:
    field_code = get_disable_field_code()
    return str(deal_data.get(field_code)) == "1"


def is_monitored_stage(stage_id: str) -> bool:
    return stage_id in get_monitored_stages()


def is_within_working_hours(now=None) -> bool:
    now = now or timezone.localtime()
    start_hour = getattr(settings, "LEAD_CONTROL_WORKDAY_START_HOUR", 10)
    end_hour = getattr(settings, "LEAD_CONTROL_WORKDAY_END_HOUR", 19)
    return start_hour <= now.hour < end_hour


def get_end_of_today_deadline(now=None) -> str:
    now = now or timezone.localtime()
    end_of_day = now.replace(hour=23, minute=59, second=0, microsecond=0)
    return end_of_day.isoformat(timespec="seconds")


def get_allowed_attempts_for_today(monitor: LeadMonitor, now=None) -> int:
    """
    Правила:
    - если лид поступил 10:00-13:00 -> 3 попытки в этот день
    - если 13:00-16:00 -> 2 попытки
    - если 16:00-19:00 -> 1 попытка
    - на следующий день и далее -> до 3 попыток в день
    """
    now = now or timezone.localtime()

    if not monitor.entered_logic_at:
        return 0

    entered_at = timezone.localtime(monitor.entered_logic_at)

    if entered_at.date() != now.date():
        return 3

    hour = entered_at.hour
    minute = entered_at.minute
    entered_float = hour + minute / 60

    if 10 <= entered_float < 13:
        return 3
    if 13 <= entered_float < 16:
        return 2
    if 16 <= entered_float < 19:
        return 1

    return 0


def can_create_next_attempt(monitor: LeadMonitor, now=None) -> bool:
    now = now or timezone.localtime()

    if not is_within_working_hours(now):
        return False

    monitor.reset_daily_attempts_if_needed()

    allowed_attempts = get_allowed_attempts_for_today(monitor, now)
    return monitor.attempts_today < allowed_attempts


def mark_success(monitor: LeadMonitor, comment: str):
    monitor.is_active = False
    monitor.status = LeadMonitorStatus.SUCCESS
    monitor.status_comment = comment
    monitor.last_checked_at = timezone.now()
    monitor.save(update_fields=[
        "is_active",
        "status",
        "status_comment",
        "last_checked_at",
        "updated_at",
    ])


def mark_skipped(monitor: LeadMonitor, comment: str):
    monitor.is_active = False
    monitor.status = LeadMonitorStatus.SKIPPED
    monitor.status_comment = comment
    monitor.last_checked_at = timezone.now()
    monitor.save(update_fields=[
        "is_active",
        "status",
        "status_comment",
        "last_checked_at",
        "updated_at",
    ])


def mark_error(monitor: LeadMonitor, comment: str):
    monitor.status = LeadMonitorStatus.ERROR
    monitor.status_comment = comment
    monitor.last_checked_at = timezone.now()
    monitor.save(update_fields=[
        "status",
        "status_comment",
        "last_checked_at",
        "updated_at",
    ])


def create_and_bind_typical_task(monitor: LeadMonitor, now=None) -> int:
    now = now or timezone.localtime()

    task_id = create_typical_task(
        deal_id=monitor.bitrix_deal_id,
        responsible_id=monitor.responsible_bitrix_user_id,
        auditor_id=monitor.moderator_bitrix_user_id,
        title=get_typical_task_title(),
        description=get_typical_task_description(),
        deadline=get_end_of_today_deadline(now),
    )

    monitor.bitrix_task_id = task_id
    monitor.attempts_total += 1
    monitor.attempts_today += 1
    monitor.status = LeadMonitorStatus.ACTIVE
    monitor.status_comment = ""
    monitor.last_checked_at = timezone.now()
    monitor.save(update_fields=[
        "bitrix_task_id",
        "attempts_total",
        "attempts_today",
        "status",
        "status_comment",
        "last_checked_at",
        "updated_at",
    ])

    return task_id


def should_create_moderator_task(monitor: LeadMonitor, now=None) -> bool:
    now = now or timezone.localtime()
    interval_days = get_moderator_task_interval_days()

    if not monitor.moderator_bitrix_user_id:
        return False

    if not monitor.last_moderator_task_created_at:
        if not monitor.entered_logic_at:
            return False
        entered_at = timezone.localtime(monitor.entered_logic_at)
        first_allowed_at = entered_at + timedelta(days=interval_days)
        return now >= first_allowed_at

    last_created = timezone.localtime(monitor.last_moderator_task_created_at)
    next_allowed_at = last_created + timedelta(days=interval_days)
    return now >= next_allowed_at


def resolve_moderator_task_deal_id(monitor: LeadMonitor, deal_data: dict | None = None) -> int:
    deal_data = deal_data or {}
    contact_id = deal_data.get("CONTACT_ID")
    try:
        contact_id = int(contact_id)
    except (TypeError, ValueError):
        return monitor.bitrix_deal_id

    sales_deals = find_deals_by_contact_and_category(
        contact_id,
        get_sales_deal_category_id(),
        exclude_deal_id=monitor.bitrix_deal_id,
    )
    if not sales_deals:
        return monitor.bitrix_deal_id

    sales_deal_id = sales_deals[0].get("ID")
    try:
        return int(sales_deal_id)
    except (TypeError, ValueError):
        return monitor.bitrix_deal_id


def create_periodic_moderator_task(monitor: LeadMonitor, deal_data: dict | None = None, now=None) -> int:
    now = now or timezone.localtime()
    deal_id = resolve_moderator_task_deal_id(monitor, deal_data)

    task_id = create_typical_task(
        deal_id=deal_id,
        responsible_id=monitor.moderator_bitrix_user_id,
        created_by_id=get_moderator_task_creator_id(),
        title=get_moderator_task_title(),
        description=get_moderator_task_description(),
        deadline=get_end_of_today_deadline(now),
    )

    monitor.last_moderator_task_id = task_id
    monitor.last_moderator_task_created_at = timezone.now()
    monitor.last_checked_at = timezone.now()
    monitor.save(update_fields=[
        "last_moderator_task_id",
        "last_moderator_task_created_at",
        "last_checked_at",
        "updated_at",
    ])

    return task_id


def process_monitor(monitor: LeadMonitor) -> dict:
    """
    Возвращает словарь:
    - result: основной результат обработки
    - moderator_task_created: была ли создана периодическая задача модератору
    """
    now = timezone.localtime()
    moderator_task_created = False

    try:
        with transaction.atomic():
            monitor.reset_daily_attempts_if_needed()
            monitor.save(update_fields=[
                "attempts_today",
                "attempts_last_reset_date",
                "updated_at",
            ])

        deal_data = get_deal_by_id(monitor.bitrix_deal_id)
        stage_id = (deal_data.get("STAGE_ID") or "").strip()

        monitor.current_stage_id = stage_id
        monitor.raw_deal_data = deal_data
        monitor.last_checked_at = timezone.now()
        monitor.save(update_fields=[
            "current_stage_id",
            "raw_deal_data",
            "last_checked_at",
            "updated_at",
        ])

        if is_logic_disabled(deal_data):
            mark_skipped(monitor, "Логика отключена полем в сделке")
            return {"result": "skipped", "moderator_task_created": moderator_task_created}

        if not is_monitored_stage(stage_id):
            mark_success(monitor, "Сделка ушла со стадии мониторинга")
            return {"result": "success", "moderator_task_created": moderator_task_created}

        if should_create_moderator_task(monitor, now):
            create_periodic_moderator_task(monitor, deal_data, now)
            moderator_task_created = True

        if not monitor.responsible_bitrix_user_id:
            mark_error(monitor, "Не заполнен responsible_bitrix_user_id")
            return {"result": "error", "moderator_task_created": moderator_task_created}

        if not monitor.bitrix_task_id:
            if not can_create_next_attempt(monitor, now):
                return {"result": "waiting_time", "moderator_task_created": moderator_task_created}

            create_and_bind_typical_task(monitor, now)
            return {"result": "task_created", "moderator_task_created": moderator_task_created}

        task_data = get_task_by_id(monitor.bitrix_task_id)

        if not is_task_completed(task_data):
            return {"result": "waiting_task", "moderator_task_created": moderator_task_created}

        monitor.last_task_closed_at = timezone.now()
        monitor.save(update_fields=[
            "last_task_closed_at",
            "updated_at",
        ])

        if not can_create_next_attempt(monitor, now):
            return {"result": "waiting_time", "moderator_task_created": moderator_task_created}

        create_and_bind_typical_task(monitor, now)
        return {"result": "task_created", "moderator_task_created": moderator_task_created}

    except BitrixAPIError as exc:
        mark_error(monitor, f"Bitrix API error: {exc}")
        return {"result": "error", "moderator_task_created": moderator_task_created}
    except Exception as exc:
        mark_error(monitor, f"Unexpected error: {exc}")
        return {"result": "error", "moderator_task_created": moderator_task_created}


def process_all_active_monitors() -> dict:
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

    monitors = LeadMonitor.objects.filter(is_active=True).order_by("id")

    for monitor in monitors:
        stats["total"] += 1
        result_payload = process_monitor(monitor)
        result = result_payload.get("result")
        if result in stats:
            stats[result] += 1
        if result_payload.get("moderator_task_created"):
            stats["moderator_task_created"] += 1

    return stats
