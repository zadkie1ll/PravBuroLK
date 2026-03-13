import requests
from datetime import datetime
from typing import Tuple

BITRIX_WEBHOOK_URL = "https://prav-buro.bitrix24.ru/rest/24/pa1x5irnfpbcnh27/"


def seconds_to_dhms(total_seconds: int) -> str:
    """Преобразует секунды в формат dd:hh:mm:ss"""
    days = total_seconds // 86400
    hours = (total_seconds % 86400) // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{days:02d}:{hours:02d}:{minutes:02d}:{seconds:02d}"


def get_manager_call_stats(
    manager_id: int, 
    start_date: datetime, 
    end_date: datetime
) -> Tuple[str, int]:
    """
    Возвращает статистику звонков менеджера за период.
    
    Параметры:
        manager_id — PORTAL_USER_ID менеджера в Bitrix24
        start_date — начало периода (datetime)
        end_date   — конец периода (datetime)
    
    Возвращает:
        ("dd:hh:mm:ss", количество_звонков)
    """
    # Приводим даты к московскому времени (портал .ru)
    tz_offset = "+03:00"
    start_iso = start_date.replace(hour=0, minute=0, second=0).strftime(f"%Y-%m-%dT%H:%M:%S{tz_offset}")
    end_iso   = end_date.replace(hour=23, minute=59, second=59).strftime(f"%Y-%m-%dT%H:%M:%S{tz_offset}")

    url = BITRIX_WEBHOOK_URL + "voximplant.statistic.get"

    total_duration_sec = 0
    total_calls = 0
    pagination_start = 0

    while True:
        payload = {
            "FILTER": {
                "PORTAL_USER_ID": manager_id,
                ">=CALL_START_DATE": start_iso,
                "<=CALL_START_DATE": end_iso,
            },
            "SORT": "CALL_START_DATE",
            "ORDER": "ASC",
            "start": pagination_start,
        }

        try:
            response = requests.post(url, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            raise ValueError(f"Ошибка запроса к Bitrix24: {e}")

        if "error" in data:
            raise ValueError(f"Bitrix24 вернул ошибку: {data['error']}")

        # Суммируем длительность и считаем звонки
        for call in data.get("result", []):
            duration = int(call.get("CALL_DURATION", 0) or 0)
            total_duration_sec += duration
            total_calls += 1

        # Пагинация (по 50 записей)
        next_start = data.get("next")
        if next_start and next_start != 0:
            pagination_start = next_start
        else:
            break

    time_str = seconds_to_dhms(total_duration_sec)
    return time_str, total_calls