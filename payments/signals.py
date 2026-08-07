# from django.db.models.signals import post_save
# from django.dispatch import receiver
# from datetime import datetime
# from dateutil.relativedelta import relativedelta
# from .models import Contract, InstallmentPlan, InstallmentPayment
# from .views import calculate_payments

# @receiver(post_save, sender=Contract)
# def create_installment_plan(sender, instance: Contract, created, **kwargs):
#     if created:
#         plan = InstallmentPlan.objects.create(contract=instance)
#         payments_data = calculate_payments(
#             num_payments=instance.number_of_payments,
#             total_amount=float(instance.total_amount),
#             discount=float(instance.discount),
#             start_date=instance.first_payment_date.strftime("%d.%m.%Y"),
#             first_payment=float(instance.first_payment),
#             second_payment_day=instance.preferred_payment_day
#         )
#         for number, due_date_str, amount in payments_data:
#             due_date = datetime.strptime(due_date_str, "%d.%m.%Y").date()
#             InstallmentPayment.objects.create(
#                 plan=plan,
#                 number=number,
#                 due_date=due_date,
#                 amount_due=amount
#             )
#         plan.calculated = True
#         plan.save()


import logging
from datetime import timedelta
from decimal import Decimal

import requests
from django.conf import settings
from django.db.models import Sum
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from .models import ActualPayment

logger = logging.getLogger(__name__)


def _get_bitrix_webhook_url() -> str:
    return (
        getattr(settings, "BITRIX_WEBHOOK_URL", "")
        or getattr(settings, "BITRIX_WEBHOOK", "")
    ).rstrip("/")


def _notify_accountant_installment_fully_paid(plan, client) -> None:
    accountant_id = getattr(settings, "ACCOUNTANT_BITRIX_ID", "")
    bitrix_webhook = _get_bitrix_webhook_url()
    if not accountant_id or not bitrix_webhook:
        return

    fio = f"{client.surname} {client.name} {client.middlename or ''}".strip()
    deadline = (timezone.now() + timedelta(days=1)).isoformat()

    response = requests.post(
        f"{bitrix_webhook}/tasks.task.add",
        data={
            "fields[TITLE]": f"{fio}: внесён последний платёж по рассрочке",
            "fields[DESCRIPTION]": (
                "Клиент полностью погасил рассрочку. "
                "Поздравьте клиента с окончанием рассрочки и напомните про рекомендации."
            ),
            "fields[RESPONSIBLE_ID]": accountant_id,
            "fields[DEADLINE]": deadline,
            **(
                {"fields[UF_CRM_TASK][0]": f"D_{client.bitrix_id}"}
                if client.bitrix_id
                else {}
            ),
        },
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("error"):
        logger.error(
            "Не удалось поставить задачу бухгалтеру по клиенту %s: %s",
            client.id,
            payload.get("error_description") or payload["error"],
        )


@receiver(post_save, sender=ActualPayment)
def notify_accountant_on_installment_fully_paid(sender, instance: ActualPayment, created, **kwargs):
    if not created:
        return

    plan = instance.plan
    if not plan or not plan.contract:
        return

    contract = plan.contract
    expected_total = (contract.total_amount or Decimal("0")) - (contract.discount or Decimal("0"))
    if expected_total <= 0:
        return

    paid_total = plan.actual_payments.aggregate(total=Sum("amount"))["total"] or Decimal("0")
    paid_before = paid_total - instance.amount

    if paid_before >= expected_total or paid_total < expected_total:
        return

    try:
        _notify_accountant_installment_fully_paid(plan, contract.client)
    except Exception:
        logger.exception(
            "Ошибка при постановке задачи бухгалтеру по клиенту %s", contract.client_id
        )