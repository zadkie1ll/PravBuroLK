"""Порт client_withdrawals/services.py + models.py:ClientWithdrawalRecord.save/clean."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Client, WithdrawalRecord
from . import bitrix_gateway_client as gateway
from .bitrix_gateway_client import BitrixAPIError


def get_total_tail_amount(db: Session, client_id: int) -> Decimal:
    total = (
        db.query(func.coalesce(func.sum(WithdrawalRecord.tail_amount), 0))
        .filter(WithdrawalRecord.client_id == client_id)
        .scalar()
    )
    return Decimal(total)


def get_withdrawals_page_url(client_id: int) -> str:
    return f"{settings.withdrawals_page_base_url}/clients/{client_id}/withdrawals"


def validate_amounts(withdrawal_amount: Decimal | None, transferred_amount: Decimal | None) -> None:
    """Порт ClientWithdrawalRecord.clean()."""
    if withdrawal_amount is not None and withdrawal_amount < 0:
        raise HTTPException(status_code=400, detail="Сумма снятия не может быть отрицательной.")
    if transferred_amount is not None and transferred_amount < 0:
        raise HTTPException(status_code=400, detail="Сумма перевода не может быть отрицательной.")
    if (
        withdrawal_amount is not None
        and transferred_amount is not None
        and transferred_amount > withdrawal_amount
    ):
        raise HTTPException(status_code=400, detail="Сумма перевода не может быть больше суммы снятия.")


def compute_tail_amount(withdrawal_amount: Decimal | None, transferred_amount: Decimal | None) -> Decimal:
    """Порт ClientWithdrawalRecord.save()."""
    if transferred_amount is None:
        return withdrawal_amount or Decimal("0.00")
    return (withdrawal_amount or Decimal("0.00")) - transferred_amount


def apply_record_fields(
    record: WithdrawalRecord,
    *,
    withdrawal_date,
    transfer_date,
    withdrawal_amount: Decimal | None,
    transferred_amount: Decimal | None,
    comment: str,
) -> None:
    validate_amounts(withdrawal_amount, transferred_amount)
    record.withdrawal_date = withdrawal_date
    record.transfer_date = transfer_date
    record.withdrawal_amount = withdrawal_amount
    record.transferred_amount = transferred_amount
    record.tail_amount = compute_tail_amount(withdrawal_amount, transferred_amount)
    record.comment = comment
    record.updated_at = datetime.now(timezone.utc)


def build_withdrawals_summary(db: Session, client_id: int) -> str:
    records = (
        db.query(WithdrawalRecord)
        .filter(WithdrawalRecord.client_id == client_id)
        .order_by(WithdrawalRecord.withdrawal_date.desc(), WithdrawalRecord.id.desc())
        .all()
    )
    if not records:
        return "\n".join(
            ["Списания клиента", "Записей пока нет.", f"Страница: {get_withdrawals_page_url(client_id)}"]
        )

    header = "Дата снятия | Дата перевода | Снято | Переведено | Хвост"
    separator = "-" * len(header)
    lines = [header, separator]

    for record in records:
        withdrawal_date = record.withdrawal_date.strftime("%d.%m.%Y") if record.withdrawal_date else "-"
        transfer_date = record.transfer_date.strftime("%d.%m.%Y") if record.transfer_date else "-"
        withdrawal_amount = f"{record.withdrawal_amount:.2f}" if record.withdrawal_amount is not None else "-"
        transferred_amount = f"{record.transferred_amount:.2f}" if record.transferred_amount is not None else "-"
        lines.append(
            " | ".join(
                [withdrawal_date, transfer_date, withdrawal_amount, transferred_amount, f"{record.tail_amount:.2f}"]
            )
        )

    return "\n".join(lines)


def build_withdrawals_bitrix_fields(db: Session, client_id: int) -> dict[str, str]:
    return {
        settings.bitrix_client_withdrawals_link_field.strip(): get_withdrawals_page_url(client_id),
        settings.bitrix_client_withdrawals_field.strip(): build_withdrawals_summary(db, client_id),
    }


def sync_withdrawals_to_bitrix(db: Session, client: Client) -> None:
    """Fail-soft: как и в монолите, вызывающая сторона ловит исключение и просто
    предупреждает пользователя, не откатывая уже сохранённую запись."""
    if not client.bitrix_id:
        raise BitrixAPIError(f"У клиента {client.id} отсутствует bitrix_id")

    fields = build_withdrawals_bitrix_fields(db, client.id)
    gateway.call("crm.deal.update", {"id": client.bitrix_id, "fields": fields})
