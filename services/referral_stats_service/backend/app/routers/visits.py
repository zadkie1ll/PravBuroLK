from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..auth import require_staff
from ..db import get_db
from ..models import VisitEvent
from ..schemas import DashboardStatsResponse
from ..utils import utcnow

router = APIRouter(prefix="/api", tags=["dashboard-stats"], dependencies=[Depends(require_staff)])


@router.get("/dashboard-stats", response_model=DashboardStatsResponse)
def dashboard_stats(db: Session = Depends(get_db)):
    """Соответствует clients/views.py:dashboard_stats — общее число посещений ЛК за
    период, посчитанное одним COUNT(*) вместо перебора всех DashboardVisit.visits в Python."""
    now = utcnow()

    def count_since(period_start=None) -> int:
        query = db.query(func.count(VisitEvent.id))
        if period_start is not None:
            query = query.filter(VisitEvent.visited_at >= period_start)
        return query.scalar() or 0

    return DashboardStatsResponse(
        today=count_since(now - timedelta(days=1)),
        week=count_since(now - timedelta(weeks=1)),
        month=count_since(now - timedelta(days=30)),
        all_time=count_since(),
    )
