from fastapi import APIRouter, Header, HTTPException, Query
from sqlalchemy.orm import Session
from fastapi import Depends

from ..auth import check_internal_token
from ..db import get_db
from ..models import SalesManager
from ..schemas import SalesManagerOut

# Точное совпадение путей с leadreport/views.py в монолите
# (internal_sales_managers_list / internal_sales_manager_lookup), чтобы cutover
# consumers (например call_queue_service.leadreport_client) был сменой одного base_url.
router = APIRouter(prefix="/api/internal/sales-managers", tags=["internal"])


def _require_internal(authorization: str | None) -> None:
    if not check_internal_token(authorization):
        raise HTTPException(status_code=403, detail="invalid internal token")


@router.get("/", response_model=list[SalesManagerOut])
def list_active(authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    _require_internal(authorization)
    managers = db.query(SalesManager).filter(SalesManager.is_active.is_(True)).order_by(SalesManager.name).all()
    return managers


@router.get("/lookup/", response_model=SalesManagerOut)
def lookup(
    email: str = Query(...),
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    _require_internal(authorization)
    if not email.strip():
        raise HTTPException(status_code=400, detail="email query param is required")
    manager = db.query(SalesManager).filter(SalesManager.email.ilike(email.strip())).first()
    if not manager:
        raise HTTPException(status_code=404, detail="not found")
    return manager
