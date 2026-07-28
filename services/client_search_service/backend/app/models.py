from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import relationship

from .db import Base


class StageTemplate(Base):
    """Соответствует clients/models.py:StageTemplate. Здесь нужно только имя стадии для бейджа
    в карточке результата поиска."""

    __tablename__ = "stage_templates"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)


class Client(Base):
    """Соответствует clients/models.py:Client. Только поля, нужные для поиска/списка —
    остальное (договор, платежи, эквайринг) остаётся в монолите вместе с payments/client_admin."""

    __tablename__ = "clients"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    surname = Column(String(100), nullable=False)
    middlename = Column(String(100), nullable=True)
    bitrix_id = Column(String(255), nullable=True, index=True)
    stage_id = Column(Integer, ForeignKey("stage_templates.id"), nullable=True)
    is_blocked = Column(Boolean, nullable=False, default=False)

    stage = relationship("StageTemplate")


class Contract(Base):
    """Соответствует payments/models.py:Contract."""

    __tablename__ = "contracts"

    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    total_amount = Column(Numeric(10, 2), nullable=False)
    discount = Column(Numeric(10, 2), nullable=False, default=0)
    first_payment = Column(Numeric(10, 2), nullable=False)
    first_payment_date = Column(Date, nullable=False)
    number_of_payments = Column(Integer, nullable=False)
    preferred_payment_day = Column(Integer, nullable=False, default=15)
    deposit = Column(Boolean, nullable=False, default=False)
    publication = Column(Boolean, nullable=False, default=False)
    extra_court_costs = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True))

    client = relationship("Client")


class InstallmentPlan(Base):
    """Соответствует payments/models.py:InstallmentPlan."""

    __tablename__ = "installment_plans"

    id = Column(Integer, primary_key=True)
    contract_id = Column(Integer, ForeignKey("contracts.id"), nullable=False, unique=True)
    calculated = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True))

    contract = relationship("Contract")


class InstallmentPayment(Base):
    """Соответствует payments/models.py:InstallmentPayment. amount_paid/PaymentApplication
    из монолита сюда не переносим — реальный шаблон client_payments_page.html их не
    показывает (там только number/due_date/amount_due/status)."""

    __tablename__ = "installment_payments"

    id = Column(Integer, primary_key=True)
    plan_id = Column(Integer, ForeignKey("installment_plans.id"), nullable=False)
    number = Column(Integer, nullable=False)
    due_date = Column(Date, nullable=False)
    amount_due = Column(Numeric(10, 2), nullable=False)
    amount_paid = Column(Numeric(10, 2), nullable=False, default=0)
    status = Column(String(10), nullable=False, default="pending")


class ActualPayment(Base):
    """Соответствует payments/models.py:ActualPayment."""

    __tablename__ = "actual_payments"

    id = Column(Integer, primary_key=True)
    plan_id = Column(Integer, ForeignKey("installment_plans.id"), nullable=True)
    payment_date = Column(Date, nullable=True)
    amount = Column(Numeric(10, 2), nullable=False)
    created_at = Column(DateTime(timezone=True))


class OtherPayment(Base):
    """Соответствует payments/models.py:OtherPayment."""

    __tablename__ = "other_payments"

    PAYMENT_TYPES = [
        ("deposit", "Судебный депозит"),
        ("publication", "Публикация"),
        ("post", "Почтовые расходы"),
        ("deposit_extra", "Дополнительный депозит"),
        ("publication_extra", "Дополнительная публикация"),
    ]

    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    payment_type = Column(String(20), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    is_paid = Column(Boolean, nullable=False, default=False)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True))
