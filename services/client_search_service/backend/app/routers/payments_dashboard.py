from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..auth import require_staff
from ..db import get_db
from ..models import ActualPayment, Client, Contract, InstallmentPlan
from ..schemas import PaymentsDashboardResponse, PaymentsDashboardRow, PaymentsDashboardStats

router = APIRouter(prefix="/api", tags=["payments-dashboard"], dependencies=[Depends(require_staff)])

PER_PAGE = 10


@router.get("/payments-dashboard", response_model=PaymentsDashboardResponse)
def payments_dashboard(page: int = 1, db: Session = Depends(get_db)):
    """Соответствует payments/views.py:payments_dashboard."""
    today = date.today()
    start_of_week = today - timedelta(days=today.weekday())
    start_of_month = today.replace(day=1)
    start_of_year = today.replace(month=1, day=1)

    def total_amount(*filters) -> Decimal:
        query = db.query(func.coalesce(func.sum(ActualPayment.amount), 0)).filter(*filters)
        return query.scalar() or Decimal("0")

    stats = PaymentsDashboardStats(
        day=total_amount(ActualPayment.payment_date == today),
        week=total_amount(ActualPayment.payment_date >= start_of_week),
        month=total_amount(ActualPayment.payment_date >= start_of_month),
        year=total_amount(ActualPayment.payment_date >= start_of_year),
    )

    base_query = (
        db.query(ActualPayment, Client)
        .outerjoin(InstallmentPlan, InstallmentPlan.id == ActualPayment.plan_id)
        .outerjoin(Contract, Contract.id == InstallmentPlan.contract_id)
        .outerjoin(Client, Client.id == Contract.client_id)
        .order_by(ActualPayment.payment_date.desc(), ActualPayment.id.desc())
    )

    total_count = base_query.count()
    num_pages = max(1, (total_count + PER_PAGE - 1) // PER_PAGE)
    page = max(1, min(page, num_pages))

    rows = base_query.offset((page - 1) * PER_PAGE).limit(PER_PAGE).all()

    results = [
        PaymentsDashboardRow(
            payment_date=payment.payment_date,
            amount=payment.amount,
            client_name=(
                f"{client.surname} {client.name}" + (f" {client.middlename}" if client.middlename else "")
                if client
                else None
            ),
        )
        for payment, client in rows
    ]

    return PaymentsDashboardResponse(stats=stats, results=results, page=page, num_pages=num_pages)
