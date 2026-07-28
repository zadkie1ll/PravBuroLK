from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..auth import require_staff
from ..config import settings
from ..db import get_db
from ..schemas import ReferralStatsResponse, ReferralStatRow

router = APIRouter(prefix="/api", tags=["referral-stats"], dependencies=[Depends(require_staff)])

_CLIENTS_SQL = text(
    """
    select
        c.id,
        c.surname || ' ' || c.name || ' ' || coalesce(c.middlename, '') as name,
        c.referral_code,
        coalesce(clicks.cnt, 0) as clicks,
        coalesce(apps.cnt, 0) as applications
    from clients c
    left join (
        select owner_id, count(*) as cnt from referral_clicks
        where owner_type = 'client' group by owner_id
    ) clicks on clicks.owner_id = c.id
    left join (
        select referral_owner_id, count(*) as cnt from applications
        where referral_owner_type = 'client' group by referral_owner_id
    ) apps on apps.referral_owner_id = c.id
    """
)

_EMPLOYEES_SQL = text(
    """
    select
        e.id,
        e.name,
        e.referral_code,
        coalesce(clicks.cnt, 0) as clicks,
        coalesce(apps.cnt, 0) as applications
    from employees e
    left join (
        select owner_id, count(*) as cnt from referral_clicks
        where owner_type = 'employee' group by owner_id
    ) clicks on clicks.owner_id = e.id
    left join (
        select referral_owner_id, count(*) as cnt from applications
        where referral_owner_type = 'employee' group by referral_owner_id
    ) apps on apps.referral_owner_id = e.id
    """
)


@router.get("/referral-stats", response_model=ReferralStatsResponse)
def referral_stats(
    filter: str = "all",
    sort: str = "applications",
    page: int = 1,
    per_page: int = 50,
    db: Session = Depends(get_db),
):
    """Соответствует bitrix/views.py:referral_stats — но клики/заявки считаются одним
    GROUP BY на таблицу вместо N+1 .count() на каждую строку, плюс реальная пагинация
    вместо рендера всего списка целиком."""
    stats: list[ReferralStatRow] = []

    if filter in ("all", "clients"):
        for row in db.execute(_CLIENTS_SQL):
            ref_link = f"{settings.site_base_url}/ref/{row.referral_code}/"
            stats.append(
                ReferralStatRow(
                    type="Клиент", name=row.name.strip(), ref_link=ref_link,
                    clicks=row.clicks, applications=row.applications,
                )
            )

    if filter in ("all", "employees"):
        for row in db.execute(_EMPLOYEES_SQL):
            ref_link = f"{settings.site_base_url}/ref/{row.referral_code}/"
            stats.append(
                ReferralStatRow(
                    type="Сотрудник", name=row.name, ref_link=ref_link,
                    clicks=row.clicks, applications=row.applications,
                )
            )

    stats.sort(key=lambda s: s.clicks if sort == "clicks" else s.applications, reverse=True)

    count = len(stats)
    start = (page - 1) * per_page
    page_results = stats[start : start + per_page]

    return ReferralStatsResponse(results=page_results, count=count, page=page, per_page=per_page)
