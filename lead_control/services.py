from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .bitrix_api import (
    BitrixAPIError,
    create_typical_task,
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


def process_monitor(monitor: LeadMonitor) -> str:
    """
    Возвращает:
    - success
    - skipped
    - waiting_task
    - waiting_time
    - task_created
    - error
    """
    now = timezone.localtime()

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
            return "skipped"

        if not is_monitored_stage(stage_id):
            mark_success(monitor, "Сделка ушла со стадии мониторинга")
            return "success"

        if not monitor.responsible_bitrix_user_id:
            mark_error(monitor, "Не заполнен responsible_bitrix_user_id")
            return "error"

        if not monitor.bitrix_task_id:
            if not can_create_next_attempt(monitor, now):
                return "waiting_time"

            create_and_bind_typical_task(monitor, now)
            return "task_created"

        task_data = get_task_by_id(monitor.bitrix_task_id)

        if not is_task_completed(task_data):
            return "waiting_task"

        monitor.last_task_closed_at = timezone.now()
        monitor.save(update_fields=[
            "last_task_closed_at",
            "updated_at",
        ])

        if not can_create_next_attempt(monitor, now):
            return "waiting_time"

        create_and_bind_typical_task(monitor, now)
        return "task_created"

    except BitrixAPIError as exc:
        mark_error(monitor, f"Bitrix API error: {exc}")
        return "error"
    except Exception as exc:
        mark_error(monitor, f"Unexpected error: {exc}")
        return "error"


def process_all_active_monitors() -> dict:
    stats = {
        "total": 0,
        "success": 0,
        "skipped": 0,
        "waiting_task": 0,
        "waiting_time": 0,
        "task_created": 0,
        "error": 0,
    }

    monitors = LeadMonitor.objects.filter(is_active=True).order_by("id")

    for monitor in monitors:
        stats["total"] += 1
        result = process_monitor(monitor)
        if result in stats:
            stats[result] += 1

    return stats
