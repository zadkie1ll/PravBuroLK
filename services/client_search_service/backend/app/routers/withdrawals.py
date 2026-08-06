from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import require_staff
from ..db import get_db
from ..models import Client, WithdrawalRecord
from ..schemas import WithdrawalMutationResponse, WithdrawalRecordUpsert, WithdrawalsPageResponse
from ..services import withdrawals as service
from ..services.bitrix_gateway_client import BitrixAPIError

router = APIRouter(prefix="/api", tags=["withdrawals"], dependencies=[Depends(require_staff)])


def _sync_or_warn(db: Session, client: Client) -> str | None:
    """Порт паттерна из client_withdrawals/views.py — запись уже сохранена, ошибка Bitrix
    только предупреждает, не откатывает."""
    try:
        service.sync_withdrawals_to_bitrix(db, client)
        return None
    except BitrixAPIError as exc:
        return str(exc)


@router.get("/clients/{client_id}/withdrawals", response_model=WithdrawalsPageResponse)
def get_withdrawals_page(client_id: int, db: Session = Depends(get_db)):
    client = db.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Клиент не найден")

    records = (
        db.query(WithdrawalRecord)
        .filter(WithdrawalRecord.client_id == client_id)
        .order_by(WithdrawalRecord.withdrawal_date.desc(), WithdrawalRecord.id.desc())
        .all()
    )
    total_withdrawal_amount = sum((r.withdrawal_amount or Decimal("0.00") for r in records), Decimal("0.00"))

    return WithdrawalsPageResponse(
        client=client,
        records=records,
        total_withdrawal_amount=total_withdrawal_amount,
        total_tail_amount=service.get_total_tail_amount(db, client_id),
    )


@router.post("/clients/{client_id}/withdrawals", response_model=WithdrawalMutationResponse)
def create_withdrawal_record(client_id: int, payload: WithdrawalRecordUpsert, db: Session = Depends(get_db)):
    client = db.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Клиент не найден")

    service.validate_amounts(payload.withdrawal_amount, payload.transferred_amount)

    record = WithdrawalRecord(
        client_id=client.id,
        withdrawal_date=payload.withdrawal_date,
        transfer_date=payload.transfer_date,
        withdrawal_amount=payload.withdrawal_amount,
        transferred_amount=payload.transferred_amount,
        tail_amount=service.compute_tail_amount(payload.withdrawal_amount, payload.transferred_amount),
        comment=payload.comment.strip(),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(record)
    db.commit()

    return WithdrawalMutationResponse(success=True, bitrix_warning=_sync_or_warn(db, client))


@router.put("/withdrawals/{record_id}", response_model=WithdrawalMutationResponse)
def update_withdrawal_record(record_id: int, payload: WithdrawalRecordUpsert, db: Session = Depends(get_db)):
    record = db.get(WithdrawalRecord, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Запись не найдена")

    service.apply_record_fields(
        record,
        withdrawal_date=payload.withdrawal_date,
        transfer_date=payload.transfer_date,
        withdrawal_amount=payload.withdrawal_amount,
        transferred_amount=payload.transferred_amount,
        comment=payload.comment.strip(),
    )
    db.commit()

    return WithdrawalMutationResponse(success=True, bitrix_warning=_sync_or_warn(db, record.client))


@router.delete("/withdrawals/{record_id}", response_model=WithdrawalMutationResponse)
def delete_withdrawal_record(record_id: int, db: Session = Depends(get_db)):
    record = db.get(WithdrawalRecord, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Запись не найдена")

    client = record.client
    db.delete(record)
    db.commit()

    return WithdrawalMutationResponse(success=True, bitrix_warning=_sync_or_warn(db, client))
