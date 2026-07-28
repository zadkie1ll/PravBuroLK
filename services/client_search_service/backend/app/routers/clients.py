from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..auth import require_staff
from ..config import settings
from ..db import get_db
from ..models import ActualPayment, Client, Contract, InstallmentPayment, InstallmentPlan, OtherPayment
from ..schemas import (
    ActualBulkUpdateItem,
    ActualCreate,
    ClientDetailResponse,
    ContractUpdate,
    InstallmentBulkUpdateItem,
    InstallmentCreate,
    OtherPaymentBulkUpdateItem,
    OtherPaymentCreate,
)
from ..services.tail_amount import get_total_tail_amount

router = APIRouter(prefix="/api", tags=["clients"], dependencies=[Depends(require_staff)])


def _get_or_create_plan(db: Session, contract: Contract) -> InstallmentPlan:
    """Соответствует payments/views.py:client_payments_page — "лучший" план (больше всего
    платежей), если вдруг есть дубли; иначе создаём новый."""
    plans = db.query(InstallmentPlan).filter(InstallmentPlan.contract_id == contract.id).all()
    if not plans:
        plan = InstallmentPlan(contract_id=contract.id)
        db.add(plan)
        db.commit()
        db.refresh(plan)
        return plan

    def score(p: InstallmentPlan) -> tuple[int, int, int]:
        inst_cnt = db.query(func.count(InstallmentPayment.id)).filter(InstallmentPayment.plan_id == p.id).scalar()
        act_cnt = db.query(func.count(ActualPayment.id)).filter(ActualPayment.plan_id == p.id).scalar()
        return (inst_cnt, act_cnt, p.id)

    return max(plans, key=score)


@router.get("/clients/{client_id}", response_model=ClientDetailResponse)
def client_detail(client_id: int, db: Session = Depends(get_db)):
    client = db.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Клиент не найден")

    contract = db.query(Contract).filter(Contract.client_id == client_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="У клиента нет договора")

    plan = _get_or_create_plan(db, contract)

    installments = (
        db.query(InstallmentPayment)
        .filter(InstallmentPayment.plan_id == plan.id)
        .order_by(InstallmentPayment.number)
        .all()
    )
    actuals = (
        db.query(ActualPayment)
        .filter(ActualPayment.plan_id == plan.id)
        .order_by(ActualPayment.payment_date, ActualPayment.id)
        .all()
    )
    other_payments = (
        db.query(OtherPayment)
        .filter(OtherPayment.client_id == client_id)
        .order_by(OtherPayment.created_at.desc())
        .all()
    )

    total_installments_sum = sum((p.amount_due for p in installments), Decimal("0"))
    total_actuals_sum = sum((a.amount for a in actuals), Decimal("0"))
    contract_final_amount = (contract.total_amount or Decimal("0")) - (contract.discount or Decimal("0"))

    return ClientDetailResponse(
        client=client,
        contract=contract,
        plan_id=plan.id,
        installments=installments,
        actuals=actuals,
        other_payments=other_payments,
        total_installments_sum=total_installments_sum,
        total_actuals_sum=total_actuals_sum,
        contract_final_amount=contract_final_amount,
        total_tail_amount=get_total_tail_amount(client_id),
        bitrix_deal_url=f"{settings.bitrix_deal_base_url}/{client.bitrix_id}/" if client.bitrix_id else None,
        withdrawals_url=f"{settings.monolith_client_withdrawals_url}/{client_id}/",
    )


@router.put("/contracts/{contract_id}")
def update_contract(contract_id: int, payload: ContractUpdate, db: Session = Depends(get_db)):
    """Соответствует payments/views.py:update_contract_info."""
    contract = db.get(Contract, contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Договор не найден")
    if payload.number_of_payments < 1:
        raise HTTPException(status_code=400, detail="Количество платежей должно быть больше нуля")

    contract.total_amount = payload.total_amount
    contract.discount = payload.discount
    contract.first_payment = payload.first_payment
    contract.first_payment_date = payload.first_payment_date
    contract.number_of_payments = payload.number_of_payments
    db.commit()
    return {"success": True}


@router.post("/installments")
def create_installment(payload: InstallmentCreate, db: Session = Depends(get_db)):
    """Соответствует payments/views.py:create_installment_payment."""
    plan = db.get(InstallmentPlan, payload.plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="План рассрочки не найден")

    last = (
        db.query(InstallmentPayment)
        .filter(InstallmentPayment.plan_id == plan.id)
        .order_by(InstallmentPayment.number.desc())
        .first()
    )
    next_number = (last.number + 1) if last else 1

    db.add(
        InstallmentPayment(
            plan_id=plan.id,
            number=next_number,
            due_date=payload.due_date,
            amount_due=payload.amount_due,
            status="pending",
        )
    )
    db.commit()
    return {"success": True}


@router.delete("/installments/{installment_id}")
def delete_installment(installment_id: int, db: Session = Depends(get_db)):
    """Соответствует payments/views.py:delete_installment_payment — удаляем и сдвигаем
    номера последующих платежей вниз."""
    payment = db.get(InstallmentPayment, installment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Платёж не найден")

    plan_id, deleted_number = payment.plan_id, payment.number
    db.delete(payment)
    db.flush()

    next_payments = (
        db.query(InstallmentPayment)
        .filter(InstallmentPayment.plan_id == plan_id, InstallmentPayment.number > deleted_number)
        .order_by(InstallmentPayment.number)
        .all()
    )
    for p in next_payments:
        p.number -= 1

    db.commit()
    return {"success": True}


@router.patch("/installments/bulk")
def bulk_update_installments(items: list[InstallmentBulkUpdateItem], db: Session = Depends(get_db)):
    """Соответствует payments/views.py:update_installment_payments."""
    for item in items:
        payment = db.get(InstallmentPayment, item.id)
        if not payment:
            continue
        payment.due_date = item.due_date
        payment.amount_due = item.amount_due
        payment.status = item.status
    db.commit()
    return {"success": True}


@router.post("/actuals")
def create_actual(payload: ActualCreate, db: Session = Depends(get_db)):
    """Соответствует payments/views.py:create_actual_payments."""
    plan = db.get(InstallmentPlan, payload.plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="План рассрочки не найден")

    db.add(ActualPayment(plan_id=plan.id, payment_date=payload.payment_date, amount=payload.amount))
    db.commit()
    return {"success": True}


@router.delete("/actuals/{actual_id}")
def delete_actual(actual_id: int, db: Session = Depends(get_db)):
    """Соответствует payments/views.py:delete_actual_payment_view. В монолите этот путь на
    самом деле никогда не удаляет платёж — `delete_actual_payment_view` там по ошибке зовёт
    одноимённую view-функцию (а не сервисную из utilities.py, она затенена определением ниже
    по файлу), которая падает на несовпадении сигнатуры и просто возвращает success:false.
    Здесь делаем то, что явно подразумевалось — простое удаление."""
    payment = db.get(ActualPayment, actual_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Платёж не найден")
    db.delete(payment)
    db.commit()
    return {"success": True}


@router.patch("/actuals/bulk")
def bulk_update_actuals(items: list[ActualBulkUpdateItem], db: Session = Depends(get_db)):
    """Соответствует payments/views.py:update_actual_payments."""
    for item in items:
        payment = db.get(ActualPayment, item.id)
        if not payment:
            continue
        payment.payment_date = item.payment_date
        payment.amount = item.amount
    db.commit()
    return {"success": True}


@router.post("/other-payments")
def create_other_payment(payload: OtherPaymentCreate, db: Session = Depends(get_db)):
    """Соответствует payments/views.py:create_other_payments."""
    client = db.get(Client, payload.client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Клиент не найден")

    db.add(
        OtherPayment(
            client_id=client.id,
            payment_type=payload.payment_type,
            amount=payload.amount,
            comment=payload.comment,
        )
    )
    db.commit()
    return {"success": True}


@router.delete("/other-payments/{other_id}")
def delete_other_payment(other_id: int, db: Session = Depends(get_db)):
    """Соответствует payments/views.py:delete_other_payment."""
    payment = db.get(OtherPayment, other_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Платёж не найден")
    db.delete(payment)
    db.commit()
    return {"success": True}


@router.patch("/other-payments/bulk")
def bulk_update_other_payments(items: list[OtherPaymentBulkUpdateItem], db: Session = Depends(get_db)):
    """Соответствует payments/views.py:update_other_payments."""
    for item in items:
        payment = db.get(OtherPayment, item.id)
        if not payment:
            continue
        payment.payment_type = item.payment_type
        payment.amount = item.amount
        payment.comment = item.comment
    db.commit()
    return {"success": True}
