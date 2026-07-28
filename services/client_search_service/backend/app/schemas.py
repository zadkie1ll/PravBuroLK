from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class ClientResult(BaseModel):
    id: int
    name: str
    surname: str
    middlename: str | None
    bitrix_id: str | None
    stage_name: str | None


class SearchResponse(BaseModel):
    query: str
    results: list[ClientResult]


class ClientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    surname: str
    middlename: str | None
    bitrix_id: str | None
    is_blocked: bool


class ContractOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    total_amount: Decimal
    discount: Decimal
    first_payment: Decimal
    first_payment_date: date
    number_of_payments: int
    preferred_payment_day: int


class InstallmentPaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    number: int
    due_date: date
    amount_due: Decimal
    status: str


class ActualPaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    payment_date: date | None
    amount: Decimal


class OtherPaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    payment_type: str
    amount: Decimal
    comment: str | None


class ClientDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    client: ClientOut
    contract: ContractOut
    plan_id: int
    installments: list[InstallmentPaymentOut]
    actuals: list[ActualPaymentOut]
    other_payments: list[OtherPaymentOut]
    total_installments_sum: Decimal
    total_actuals_sum: Decimal
    contract_final_amount: Decimal
    total_tail_amount: Decimal
    bitrix_deal_url: str | None
    withdrawals_url: str


class ContractUpdate(BaseModel):
    total_amount: Decimal
    discount: Decimal
    first_payment: Decimal
    first_payment_date: date
    number_of_payments: int


class InstallmentCreate(BaseModel):
    plan_id: int
    due_date: date
    amount_due: Decimal


class InstallmentBulkUpdateItem(BaseModel):
    id: int
    due_date: date
    amount_due: Decimal
    status: str


class ActualCreate(BaseModel):
    plan_id: int
    payment_date: date
    amount: Decimal


class ActualBulkUpdateItem(BaseModel):
    id: int
    payment_date: date
    amount: Decimal


class OtherPaymentCreate(BaseModel):
    client_id: int
    payment_type: str
    amount: Decimal
    comment: str | None = None


class OtherPaymentBulkUpdateItem(BaseModel):
    id: int
    payment_type: str
    amount: Decimal
    comment: str | None = None


class PaymentsDashboardStats(BaseModel):
    day: Decimal
    week: Decimal
    month: Decimal
    year: Decimal


class PaymentsDashboardRow(BaseModel):
    payment_date: date | None
    amount: Decimal
    client_name: str | None


class PaymentsDashboardResponse(BaseModel):
    stats: PaymentsDashboardStats
    results: list[PaymentsDashboardRow]
    page: int
    num_pages: int
