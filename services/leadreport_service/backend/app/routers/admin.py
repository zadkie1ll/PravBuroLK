from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..auth import require_staff
from ..db import get_db
from ..models import LeadSource, SalesManager, User
from ..schemas import (
    IsActivePatch,
    LeadSourceAdminRow,
    LeadSourceListResponse,
    ManagerStats,
    SalesManagerAdminRow,
    SalesManagerListResponse,
    SyncResult,
)
from ..services.bitrix_client import BitrixAPIError
from ..services.call_stats import get_manager_call_stats
from ..services.sync import sync_sales_managers_from_bitrix, sync_sources_from_bitrix

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_staff)])


def _parse_period(start_str: str | None, end_str: str | None) -> tuple[datetime, datetime]:
    today = date.today()
    if start_str and end_str:
        try:
            start = datetime.strptime(start_str, "%Y-%m-%d")
            end = datetime.strptime(end_str, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
            return start, end
        except ValueError:
            pass
    return (
        datetime.combine(today, datetime.min.time()),
        datetime.combine(today, datetime.max.time()),
    )


@router.get("/dashboard")
def dashboard(start: str | None = None, end: str | None = None, db: Session = Depends(get_db)):
    """Соответствует leadreport/views.py:lead_admin_dashboard."""
    period_start, period_end = _parse_period(start, end)
    managers = (
        db.query(SalesManager)
        .filter(SalesManager.is_active.is_(True), SalesManager.bitrix_user_id.isnot(None))
        .order_by(SalesManager.name)
        .all()
    )

    stats = []
    try:
        for mgr in managers:
            tt, cc = get_manager_call_stats(mgr.bitrix_user_id, period_start, period_end)
            stats.append({"manager": mgr, "total_time": tt or "0 мин", "call_count": cc or 0})
    except BitrixAPIError as exc:
        raise HTTPException(status_code=502, detail=f"Bitrix недоступен: {exc}") from exc

    return {
        "stats": stats,
        "period_start": period_start.date().isoformat(),
        "period_end": period_end.date().isoformat(),
    }


@router.get("/managers/{manager_id}", response_model=ManagerStats)
def manager_detail(
    manager_id: int,
    start: str | None = None,
    end: str | None = None,
    db: Session = Depends(get_db),
):
    """Соответствует leadreport/views.py:lead_admin_manager_detail."""
    manager = (
        db.query(SalesManager)
        .filter(SalesManager.id == manager_id, SalesManager.is_active.is_(True))
        .first()
    )
    if not manager:
        raise HTTPException(status_code=404, detail="not found")

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


@router.post("/sync/managers", response_model=SyncResult)
def sync_managers(db: Session = Depends(get_db)):
    try:
        return sync_sales_managers_from_bitrix(db)
    except BitrixAPIError as exc:
        raise HTTPException(status_code=502, detail=f"Bitrix недоступен: {exc}") from exc


@router.post("/sync/sources", response_model=SyncResult)
def sync_sources(db: Session = Depends(get_db)):
    try:
        return sync_sources_from_bitrix(db)
    except BitrixAPIError as exc:
        raise HTTPException(status_code=502, detail=f"Bitrix недоступен: {exc}") from exc


# --- Аналог Django admin changelist для SalesManager/LeadSource
# (leadreport/admin.py: SalesManagerAdmin/LeadSourceAdmin) ---


@router.get("/managers-list", response_model=SalesManagerListResponse)
def managers_list(
    search: str = "",
    is_active: bool | None = None,
    page: int = 1,
    db: Session = Depends(get_db),
):
    """Соответствует SalesManagerAdmin: list_display, search_fields, list_filter(is_active),
    ordering=("name",), list_per_page=50."""
    per_page = 50
    query = db.query(SalesManager, User.username).outerjoin(User, User.id == SalesManager.user_id)

    if is_active is not None:
        query = query.filter(SalesManager.is_active.is_(is_active))

    if search.strip():
        term = f"%{search.strip()}%"
        conditions = [
            SalesManager.name.ilike(term),
            SalesManager.email.ilike(term),
            SalesManager.phone.ilike(term),
            SalesManager.megafon_user.ilike(term),
            SalesManager.megafon_group.ilike(term),
            SalesManager.megafon_clid.ilike(term),
            User.username.ilike(term),
        ]
        if search.strip().isdigit():
            conditions.append(SalesManager.bitrix_user_id == int(search.strip()))
        query = query.filter(or_(*conditions))

    count = query.count()
    rows = (
        query.order_by(SalesManager.name)
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    results = [
        SalesManagerAdminRow(
            id=m.id,
            name=m.name,
            bitrix_user_id=m.bitrix_user_id,
            megafon_user=m.megafon_user,
            megafon_clid=m.megafon_clid,
            email=m.email,
            phone=m.phone,
            user_username=username,
            is_active=m.is_active,
            updated_at=m.updated_at,
        )
        for m, username in rows
    ]
    return SalesManagerListResponse(results=results, count=count, page=page, per_page=per_page)


@router.patch("/managers-list/{manager_id}", response_model=SalesManagerAdminRow)
def managers_list_patch(manager_id: int, payload: IsActivePatch, db: Session = Depends(get_db)):
    """list_editable = ("is_active",) в SalesManagerAdmin."""
    manager = db.get(SalesManager, manager_id)
    if not manager:
        raise HTTPException(status_code=404, detail="not found")
    manager.is_active = payload.is_active
    db.commit()
    db.refresh(manager)
    username = None
    if manager.user_id:
        username = db.query(User.username).filter(User.id == manager.user_id).scalar()
    return SalesManagerAdminRow(
        id=manager.id,
        name=manager.name,
        bitrix_user_id=manager.bitrix_user_id,
        megafon_user=manager.megafon_user,
        megafon_clid=manager.megafon_clid,
        email=manager.email,
        phone=manager.phone,
        user_username=username,
        is_active=manager.is_active,
        updated_at=manager.updated_at,
    )


@router.get("/sources-list", response_model=LeadSourceListResponse)
def sources_list(
    search: str = "",
    is_active: bool | None = None,
    page: int = 1,
    db: Session = Depends(get_db),
):
    """Соответствует LeadSourceAdmin: list_display, search_fields, list_filter(is_active),
    ordering=("name",)."""
    per_page = 100
    query = db.query(LeadSource)

    if is_active is not None:
        query = query.filter(LeadSource.is_active.is_(is_active))

    if search.strip():
        term = f"%{search.strip()}%"
        conditions = [LeadSource.name.ilike(term)]
        if search.strip().isdigit():
            conditions.append(LeadSource.bitrix_id == int(search.strip()))
        query = query.filter(or_(*conditions))

    count = query.count()
    rows = (
        query.order_by(LeadSource.name)
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return LeadSourceListResponse(
        results=[LeadSourceAdminRow.model_validate(s, from_attributes=True) for s in rows],
        count=count,
        page=page,
        per_page=per_page,
    )


@router.patch("/sources-list/{source_id}", response_model=LeadSourceAdminRow)
def sources_list_patch(source_id: int, payload: IsActivePatch, db: Session = Depends(get_db)):
    """list_editable = ("is_active",) в LeadSourceAdmin."""
    source = db.get(LeadSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="not found")
    source.is_active = payload.is_active
    db.commit()
    db.refresh(source)
    return LeadSourceAdminRow.model_validate(source, from_attributes=True)
