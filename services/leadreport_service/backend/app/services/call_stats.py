from datetime import datetime

from .bitrix_client import BitrixClient


def seconds_to_dhms(total_seconds: int) -> str:
    days = total_seconds // 86400
    hours = (total_seconds % 86400) // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{days:02d}:{hours:02d}:{minutes:02d}:{seconds:02d}"


def get_manager_call_stats(manager_id: int, start_date: datetime, end_date: datetime) -> tuple[str, int]:
    """Портировано из leadreport/services/pick_manager_calls.py. Раньше слало запросы
    напрямую в захардкоженный Bitrix webhook, теперь идёт через bitrix_gateway_service."""
    tz_offset = "+03:00"
    start_iso = start_date.replace(hour=0, minute=0, second=0).strftime(f"%Y-%m-%dT%H:%M:%S{tz_offset}")
    end_iso = end_date.replace(hour=23, minute=59, second=59).strftime(f"%Y-%m-%dT%H:%M:%S{tz_offset}")

    client = BitrixClient()
    calls = client.paginated_call(
        "voximplant.statistic.get",
        {
            "FILTER": {
                "PORTAL_USER_ID": manager_id,
                ">=CALL_START_DATE": start_iso,
                "<=CALL_START_DATE": end_iso,
            },
            "SORT": "CALL_START_DATE",
            "ORDER": "ASC",
        },
    )

    total_duration_sec = sum(int(call.get("CALL_DURATION", 0) or 0) for call in calls)
    return seconds_to_dhms(total_duration_sec), len(calls)
