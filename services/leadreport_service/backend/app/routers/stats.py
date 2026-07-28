from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..db import get_db
from ..models import SalesManager, User
from ..schemas import ManagerStats
from ..services.bitrix_client import BitrixAPIError
from ..services.call_stats import get_manager_call_stats

router = APIRouter(prefix="/stats", tags=["stats"])


def _parse_period(start_str: str | None, end_str: str | None) -> tuple[datetime, datetime]:
    today = date.today()
    if start_str and end_str:
        try:
            return (
                datetime.strptime(start_str, "%Y-%m-%dT%H:%M"),
                datetime.strptime(end_str, "%Y-%m-%dT%H:%M"),
            )
        except ValueError:
            pass
    return (
        datetime.combine(today, datetime.min.time()),
        datetime.combine(today, datetime.max.time()),
    )


@router.get("/me", response_model=ManagerStats)
def my_stats(
    start: str | None = None,
    end: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Соответствует leadreport/views.py:lead_my_stats_page."""
    manager = db.query(SalesManager).filter(SalesManager.user_id == current_user.id).first()
    if not manager:
        raise HTTPException(status_code=404, detail="У вас нет профиля менеджера продаж")

    period_start, period_end = _parse_period(start, end)
    try:
        total_time, call_count = get_manager_call_stats(manager.bitrix_user_id, period_start, period_end)
    except BitrixAPIError as exc:
        raise HTTPException(status_code=502, detail=f"Bitrix недоступен: {exc}") from exc

    return ManagerStats(
        manager=manager,
        period_start=period_start,
        period_end=period_end,
        total_time=total_time or "0 мин",
        call_count=call_count or 0,
    )
