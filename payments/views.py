from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from datetime import datetime
from dateutil.relativedelta import relativedelta
from django.contrib.auth.decorators import user_passes_test
from decimal import Decimal, InvalidOperation
from django.http import JsonResponse, HttpResponseForbidden
from django.db import transaction
from django.urls import reverse
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.db import models
from django.db.models import Count
from django.db.models.functions import Lower
from django.db.models import Sum
from django.utils import timezone
from django.views import View
from .sync_payments_service import sync_client_to_bitrix
from datetime import date, timedelta
import time
from clients.models import Client
import requests
from django.core.paginator import Paginator
from django.utils.timezone import now
import json
from django.utils.decorators import method_decorator
from django.http import JsonResponse
from django.db.models import Q
from .models import Contract, InstallmentPlan, InstallmentPayment, ActualPayment, OtherPayment
from django.contrib.auth.decorators import login_required
from django.db.models.functions import Cast
from django.db.models import CharField
from django.db import connection
import re
from .utilities import get_deal_data_from_bitrix, russian_to_translit, recreate_actual_payment, delete_actual_payment
import telebot
from client_withdrawals.services import build_withdrawals_bitrix_fields


BOT_TOKEN = "8208949436:AAEIzi6eP5R04crpwpIchWnpqCCFv8TROvY"
CHAT_ID = "-4907127148"


def _extract_contract_deal_id_from_order(order_number: str) -> int | None:
    match = re.match(r"^contract-(\d+)-\d+$", str(order_number or ""))
    if not match:
        return None
    return int(match.group(1))


def _get_bitrix_webhook_url() -> str:
    bitrix_webhook = (
        getattr(settings, "BITRIX_WEBHOOK_URL", "")
        or getattr(settings, "BITRIX_WEBHOOK", "")
    ).rstrip("/")
    if not bitrix_webhook:
        raise RuntimeError("BITRIX_WEBHOOK_URL is not configured")
    return bitrix_webhook


def _add_bitrix_timeline_comment_for_deal(deal_id: int, comment: str) -> None:
    bitrix_webhook = _get_bitrix_webhook_url()

    response = requests.post(
        f"{bitrix_webhook}/crm.timeline.comment.add",
        data={
            "fields[ENTITY_ID]": str(deal_id),
            "fields[ENTITY_TYPE]": "deal",
            "fields[COMMENT]": comment,
        },
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("error"):
        raise RuntimeError(payload.get("error_description") or payload["error"])


def _get_bitrix_deal(deal_id: int) -> dict:
    bitrix_webhook = _get_bitrix_webhook_url()
    response = requests.get(
        f"{bitrix_webhook}/crm.deal.get",
        params={"ID": str(deal_id)},
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("error"):
        raise RuntimeError(payload.get("error_description") or payload["error"])
    return payload.get("result") or {}


def _add_contract_payment_task_for_deal(deal_id: int) -> int | None:
    deal = _get_bitrix_deal(deal_id)
    responsible_id = str(deal.get("ASSIGNED_BY_ID") or "").strip()
    if not responsible_id:
        raise RuntimeError(f"Deal {deal_id} has no ASSIGNED_BY_ID")

    deadline = (timezone.now() + timedelta(days=1)).isoformat()
    bitrix_webhook = _get_bitrix_webhook_url()
    response = requests.post(
        f"{bitrix_webhook}/tasks.task.add",
        data={
            "fields[TITLE]": "Клиент внес оплату",
            "fields[DESCRIPTION]": "Клиент внес оплату, необходимо перевести его в отдел сопровождения",
            "fields[RESPONSIBLE_ID]": responsible_id,
            "fields[DEADLINE]": deadline,
        },
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("error"):
        raise RuntimeError(payload.get("error_description") or payload["error"])
    result = payload.get("result") or {}
    task = result.get("task") if isinstance(result, dict) else None
    task_id = (task or {}).get("id") if isinstance(task, dict) else result
    try:
        return int(task_id)
    except (TypeError, ValueError):
        return None


def _handle_contract_payment_callback(order_number: str, amount: Decimal) -> JsonResponse:
    deal_id = _extract_contract_deal_id_from_order(order_number)
    if not deal_id:
        return JsonResponse({"error": f"Invalid contract payment orderNumber: {order_number}"}, status=400)

    comment = (
        "Поступила успешная оплата по договору\n"
        f"Сумма: {amount} ₽\n"
        f"Номер платежа: {order_number}"
    )
    _add_bitrix_timeline_comment_for_deal(deal_id, comment)
    task_id = _add_contract_payment_task_for_deal(deal_id)

    return JsonResponse(
        {
            "status": "success",
            "deal_id": deal_id,
            "orderNumber": order_number,
            "amount": str(amount),
            "comment_added": True,
            "task_created": True,
            "task_id": task_id,
        },
        status=200,
    )


@csrf_exempt
def calculate_payments(num_payments, total_amount, discount, start_date, first_payment, second_payment_day):
    if num_payments == 1 and first_payment >= (total_amount - discount):
        return [[1, start_date, f"{first_payment:.2f}"]]

    remaining_amount = (total_amount - discount) - first_payment
    remaining_payments = num_payments - 1

    if remaining_payments == 0:
        return [[1, start_date, f"{first_payment:.2f}"]]

    payment_amount = round(remaining_amount / remaining_payments, -2)
    adjusted_total = first_payment + payment_amount * (remaining_payments - 1)
    last_payment = (total_amount - discount) - adjusted_total 

    first_date = datetime.strptime(start_date, "%d.%m.%Y").date()
    table_data = [[1, first_date.strftime("%d.%m.%Y"), f"{first_payment:.2f}"]]

    second_payment_day = int(second_payment_day)  
    second_date = (first_date + relativedelta(months=1)).replace(day=second_payment_day)
    while second_date.day != second_payment_day:
        second_date -= relativedelta(days=1)

    table_data.append([2, second_date.strftime("%d.%m.%Y"), f"{payment_amount:.2f}"])

    current_date = second_date
    for i in range(2, num_payments - 1):  
        current_date += relativedelta(months=1)
        while current_date.day != second_payment_day:
            current_date -= relativedelta(days=1)
        
        table_data.append([i + 1, current_date.strftime("%d.%m.%Y"), f"{payment_amount:.2f}"])

    current_date += relativedelta(months=1)
    while current_date.day != second_payment_day:
        current_date -= relativedelta(days=1)

    table_data.append([num_payments, current_date.strftime("%d.%m.%Y"), f"{last_payment:.2f}"])

    return table_data


@transaction.atomic
def delete_installment_payment(request, pk):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=400)

    payment = get_object_or_404(InstallmentPayment, pk=pk)
    plan = payment.plan
    deleted_number = payment.number

    # Удаляем
    payment.delete()

    # Сдвигаем все последующие номера вниз
    next_payments = (
        InstallmentPayment.objects
        .filter(plan=plan, number__gt=deleted_number)
        .order_by("number")
    )

    for p in next_payments:
        p.number -= 1
        p.save()

    return JsonResponse({"success": True})


@transaction.atomic
def update_installment_payments(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=400)

    for key, value in request.POST.items():

        # ищем ключи: installment_{id}_{field}
        if not key.startswith("installment_"):
            continue

        _, id_str, field = key.split("_")
        iid = int(id_str)

        try:
            inst = InstallmentPayment.objects.get(pk=iid)
        except InstallmentPayment.DoesNotExist:
            continue

        if field == "date":
            inst.due_date = value

        elif field == "amount":
            inst.amount_due = value

        elif field == "status":
            inst.status = value

        inst.save()

    return JsonResponse({"success": True})


@transaction.atomic
def delete_actual_payment(request, pk):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=400)

    payment = get_object_or_404(ActualPayment, pk=pk)
    payment.delete()

    return JsonResponse({"success": True})

@transaction.atomic
def update_actual_payments(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=400)

    for key, value in request.POST.items():

        if not key.startswith("actual_"):
            continue

        _, id_str, field = key.split("_")
        iid = int(id_str)

        try:
            ap = ActualPayment.objects.get(pk=iid)
        except ActualPayment.DoesNotExist:
            continue

        if field == "date":
            ap.payment_date = value

        elif field == "amount":
            ap.amount = value

        ap.save()

    return JsonResponse({"success": True})



@require_POST
def create_installment_payment(request):

    plan_id = request.POST.get("plan_id") or request.GET.get("plan_id")
    plan = get_object_or_404(InstallmentPlan, id=plan_id)

    date = request.POST.get("new_installment_date")
    amount = request.POST.get("new_installment_amount")

    if not date or not amount:
        return JsonResponse({"success": False, "error": "Missing fields"})

    # получаем следующий номер платежа
    last = plan.payments.order_by("-number").first()
    next_number = (last.number + 1) if last else 1

    InstallmentPayment.objects.create(
        plan=plan,
        number=next_number,
        due_date=date,
        amount_due=Decimal(amount),
        status="pending"
    )

    return redirect(request.META.get("HTTP_REFERER", "/"))



def update_contract_info(request, contract_id):
    contract = get_object_or_404(Contract, id=contract_id)

    if request.method == "POST":
        try:
            total_amount = Decimal(request.POST.get("total_amount", "0"))
            discount = Decimal(request.POST.get("discount", "0"))
            first_payment = Decimal(request.POST.get("first_payment", "0"))
            first_payment_date = datetime.strptime(request.POST.get("first_payment_date", ""), "%Y-%m-%d").date()
            number_of_payments = int(request.POST.get("number_of_payments", "1"))

            if number_of_payments < 1:
                raise ValueError("Количество платежей должно быть больше нуля")

            contract.total_amount = total_amount
            contract.discount = discount
            contract.first_payment = first_payment
            contract.first_payment_date = first_payment_date
            contract.number_of_payments = number_of_payments
            contract.save()

            messages.success(request, "Изменения сохранены.")
        except Exception as e:
            messages.error(request, f"Ошибка сохранения: {e}")

        return redirect(request.META.get("HTTP_REFERER", "/"))

    return redirect("/")


@require_POST
def create_actual_payments(request):

    plan_id = request.POST.get("plan_id") or request.GET.get("plan_id")
    plan = None

    if plan_id:
        plan = get_object_or_404(InstallmentPlan, id=plan_id)

    date = request.POST.get("new_actual_date")
    amount = request.POST.get("new_actual_amount")

    if not date or not amount:
        return JsonResponse({"success": False, "error": "Missing fields"})

    ActualPayment.objects.create(
        plan=plan,
        payment_date=date,
        amount=Decimal(amount)
    )

    return redirect(request.META.get("HTTP_REFERER", "/"))


def client_payments_page(request, client_id):
    contract = get_object_or_404(Contract, client__id=client_id)
    client = contract.client

    # 1) Берём "лучший" план: тот, где больше всего платежей (если вдруг есть дубли)
    plan = (
        InstallmentPlan.objects
        .filter(contract=contract)
        .annotate(inst_cnt=Count("payments"), act_cnt=Count("actual_payments"))
        .order_by("-inst_cnt", "-act_cnt", "-id")
        .first()
    )

    # 2) Если плана вообще нет — тогда создаём (редкий случай)
    if plan is None:
        plan = InstallmentPlan.objects.create(contract=contract)

    installments = InstallmentPayment.objects.filter(plan=plan).order_by("number")

    # ---- ФИЛЬТР ПО ДАТЕ ----
    date_from = request.GET.get("actual_from")
    date_to = request.GET.get("actual_to")

    actuals = ActualPayment.objects.filter(plan=plan)
    if date_from:
        actuals = actuals.filter(payment_date__gte=date_from)
    if date_to:
        actuals = actuals.filter(payment_date__lte=date_to)

    # ВАЖНО: больше не перезатираем actuals!
    actuals = actuals.order_by("payment_date", "id")

    total_installments_sum = installments.aggregate(models.Sum("amount_due"))["amount_due__sum"] or 0
    total_actuals_sum = actuals.aggregate(models.Sum("amount"))["amount__sum"] or 0

    contract_final_amount = (contract.total_amount or 0) - (contract.discount or 0)

    other_payments = OtherPayment.objects.filter(client__id=client_id).order_by("-created_at")

    return render(request, "client_payments_page.html", {
        "client": client,
        "contract": contract,
        "plan": plan,

        "installments": installments,
        "actuals": actuals,

        "total_installments_sum": total_installments_sum,
        "total_actuals_sum": total_actuals_sum,

        "contract_final_amount": contract_final_amount,
        "other_payments": other_payments,

        "date_from": date_from,
        "date_to": date_to,
    })


@require_POST
def create_other_payments(request):
    client_id = request.POST.get("client_id")
    payment_type = request.POST.get("payment_type")
    amount = request.POST.get("new_other_amount")
    comment = request.POST.get("new_other_comment")

    if not client_id or not payment_type or not amount:
        return redirect(request.META.get("HTTP_REFERER", "/"))

    try:
        amount = Decimal(amount)
    except:
        return redirect(request.META.get("HTTP_REFERER", "/"))

    client = get_object_or_404(Client, id=client_id)

    OtherPayment.objects.create(
        client=client,
        payment_type=payment_type,
        amount=amount,
        comment=comment
    )

    # ⬅⬅⬅ Вот тут
    return redirect(request.META.get("HTTP_REFERER", "/"))




def delete_other_payment(request, payment_id):
    if request.method == "POST":
        try:
            obj = OtherPayment.objects.get(id=payment_id)
            obj.delete()
            return JsonResponse({"success": True})
        except OtherPayment.DoesNotExist:
            return JsonResponse({"success": False, "error": "Not found"})

    return JsonResponse({"success": False, "error": "Invalid method"})




def update_other_payments(request):
    if request.method == "POST":

        for key, value in request.POST.items():

            if key.startswith("other_") and key.endswith("_type"):
                payment_id = key.split("_")[1]
                obj = OtherPayment.objects.get(id=payment_id)

                obj.payment_type = value

                # Сумма
                amount_key = f"other_{payment_id}_amount"
                if amount_key in request.POST:
                    obj.amount = request.POST.get(amount_key)

                # Комментарий
                comment_key = f"other_{payment_id}_comment"
                if comment_key in request.POST:
                    obj.comment = request.POST.get(comment_key)

                # Оплачен
                paid_key = f"other_{payment_id}_is_paid"
                obj.is_paid = paid_key in request.POST

                obj.save()

        return JsonResponse({"success": True})

    return JsonResponse({"success": False, "error": "Invalid method"})



def payments_dashboard(request):
    """Статистика фактических платежей и список последних с ФИО клиента"""
    today = timezone.now().date()

    # Диапазоны дат
    start_of_week = today - timedelta(days=today.weekday())
    start_of_month = today.replace(day=1)
    start_of_year = today.replace(month=1, day=1)

    def total_amount(qs):
        return qs.aggregate(total=Sum("amount"))["total"] or Decimal("0")

    stats = {
        "day": total_amount(ActualPayment.objects.filter(payment_date=today)),
        "week": total_amount(ActualPayment.objects.filter(payment_date__gte=start_of_week)),
        "month": total_amount(ActualPayment.objects.filter(payment_date__gte=start_of_month)),
        "year": total_amount(ActualPayment.objects.filter(payment_date__gte=start_of_year)),
    }

    # Последние платежи с подгрузкой клиента через contract
    payments_qs = (
        ActualPayment.objects
        .select_related("plan__contract__client")  # <-- правильная цепочка
        .order_by("-payment_date", "-id")
    )

    paginator = Paginator(payments_qs, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "payments_stats.html",
        {
            "stats": stats,
            "page_obj": page_obj,
        },
    )


@csrf_exempt
@login_required
def client_admin_view(request, client_id):
    client = get_object_or_404(Client, pk=client_id)
    contract = Contract.objects.filter(client=client).first()
    plan = InstallmentPlan.objects.filter(contract=contract).first() if contract else None
    payments = plan.payments.all().order_by('due_date', 'id') if plan else []

    # ✅ теперь учитываем частичные оплаты
    paid_sum = (
        plan.payments.filter(amount_paid__gt=0).aggregate(total=Sum('amount_paid'))['total']
        if plan else 0
    ) or 0

    actual_payments = ActualPayment.objects.filter(plan__contract=contract) if contract else []
    other_payments = client.other_payments.all()
    expected_total = contract.total_amount - contract.discount if contract else 0

    payments_data = []
    for p in payments:
        applications = p.applications.all()
        total_paid = sum(app.applied_amount for app in applications)
        payments_data.append({
            "payment": p,
            "applications": applications,
            "total_paid": total_paid,
        })

    if request.method == "POST":
        client.name = request.POST.get("name", client.name)
        client.surname = request.POST.get("surname", client.surname)
        client.middlename = request.POST.get("middlename", client.middlename)
        client.save()

        if contract:
            preferred_day = request.POST.get("second_payment_day")
            if preferred_day and preferred_day.isdigit():
                contract.preferred_payment_day = int(preferred_day)
                contract.save()

        messages.success(request, "Данные клиента обновлены.")
        return redirect('client_admin_view', client_id=client.id)

    return render(request, "client_admin.html", {
        "client": client,
        "contract": contract,
        "plan": plan,
        "payments_data": payments_data,
        "actual_payments": actual_payments,
        "paid_sum": paid_sum,
        "expected_total": expected_total,
        "other_payments": other_payments,
    })




@csrf_exempt
@login_required
def save_actual_payment(request, payment_id):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Только POST"}, status=405)

    payment = ActualPayment.objects.filter(pk=payment_id).first()
    if not payment:
        return JsonResponse({"success": False, "error": "Платёж не найден"}, status=404)

    payment_date = request.POST.get("payment_date")
    amount_str = request.POST.get("amount", "").replace(",", ".").strip()

    if not payment_date or not amount_str:
        return JsonResponse({"success": False, "error": "Не указана дата или сумма"}, status=400)

    try:
        amount_decimal = Decimal(amount_str)
    except InvalidOperation:
        return JsonResponse({"success": False, "error": f"Неверная сумма: {amount_str}"}, status=400)

    try:
        payment_date_obj = datetime.strptime(payment_date, "%Y-%m-%d").date()
    except ValueError:
        return JsonResponse({"success": False, "error": f"Неверная дата: {payment_date}"}, status=400)

    try:
        new_payment = recreate_actual_payment(payment, amount_decimal, payment_date_obj)
        return JsonResponse({
            "success": True,
            "new_id": new_payment.id,
            "payment_date": new_payment.payment_date.strftime("%Y-%m-%d"),
            "amount": str(new_payment.amount)
        })
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)
    

@csrf_exempt
@require_POST
def recalculate_installment(request, client_id):
    client = get_object_or_404(Client, pk=client_id)
    contract = Contract.objects.filter(client=client).first()

    if not contract:
        messages.error(request, "У клиента нет контракта.")
        return redirect("client_admin_view", client_id=client.id)

    plan, _ = InstallmentPlan.objects.get_or_create(contract=contract)

    try:
        deposit_checked = request.POST.get("deposit") == "on"
        publication_checked = request.POST.get("publication") == "on"
        extra_costs_checked = request.POST.get("extra_court_costs") == "on"  # новое поле

        total_amount = Decimal(request.POST.get("total_amount", "0"))
        discount = Decimal(request.POST.get("discount", "0"))
        first_payment = Decimal(request.POST.get("first_payment", "0"))
        number_of_payments = int(request.POST.get("number_of_payments", "1"))
        first_payment_date = datetime.strptime(request.POST.get("first_payment_date"), "%Y-%m-%d").date()
        second_payment_day = int(request.POST.get("second_payment_day", 15))

        base_total = contract.total_amount

        if deposit_checked != contract.deposit:
            contract.deposit = deposit_checked

        if publication_checked != contract.publication:
            contract.publication = publication_checked

        if extra_costs_checked != getattr(contract, "extra_court_costs", False):
            contract.extra_court_costs = extra_costs_checked

        contract.total_amount = total_amount
        contract.discount = discount
        contract.first_payment = first_payment
        contract.number_of_payments = number_of_payments
        contract.first_payment_date = first_payment_date
        contract.preferred_payment_day = second_payment_day
        contract.save()

    except Exception as e:
        messages.error(request, f"Ошибка чтения данных из формы: {e}")
        return redirect("client_admin_view", client_id=client.id)

    paid_payments = plan.payments.filter(status='paid').order_by('number')
    paid_amount = paid_payments.aggregate(total=Sum('amount_due'))['total'] or Decimal('0')

    plan.payments.exclude(status='paid').delete()

    remaining_payments = number_of_payments - paid_payments.count()
    if remaining_payments <= 0:
        messages.info(request, "Все платежи уже оплачены.")
        return redirect("client_admin_view", client_id=client.id)

    include_first_payment = not paid_payments.filter(number=1).exists()
    remaining_amount = total_amount - discount - paid_amount

    if include_first_payment:
        remaining_amount -= first_payment
        if remaining_amount < 0:
            remaining_amount = Decimal('0')

    last_paid_date = paid_payments.last().due_date if paid_payments.exists() else first_payment_date
    next_payment_date = (last_paid_date + relativedelta(months=1)).replace(day=second_payment_day)
    while next_payment_date.day != second_payment_day:
        next_payment_date -= relativedelta(days=1)

    payments_to_create = remaining_payments - (1 if include_first_payment else 0)
    if payments_to_create < 0:
        payments_to_create = 0

    if payments_to_create > 0:
        payment_amount = round(remaining_amount / payments_to_create, -2)
        adjusted_total = payment_amount * (payments_to_create - 1)
        last_payment_amount = remaining_amount - adjusted_total
    else:
        payment_amount = Decimal('0')
        last_payment_amount = Decimal('0')

    new_number = paid_payments.count() + 1

    if include_first_payment:
        InstallmentPayment.objects.create(
            plan=plan,
            number=new_number,
            due_date=first_payment_date,
            amount_due=first_payment,
            status='pending'
        )
        new_number += 1

    for i in range(payments_to_create):
        amount = payment_amount if i < payments_to_create - 1 else last_payment_amount
        due_date = next_payment_date + relativedelta(months=i)
        while due_date.day != second_payment_day:
            due_date -= relativedelta(days=1)

        InstallmentPayment.objects.create(
            plan=plan,
            number=new_number + i,
            due_date=due_date,
            amount_due=amount,
            status='pending'
        )

    plan.calculated = True
    plan.save()

    try:
        sync_client_to_bitrix(client)
        messages.success(request, "Рассрочка пересчитана и данные успешно обновлены в Bitrix24.")
    except Exception as e:
        messages.warning(request, f"Рассрочка пересчитана, но не удалось обновить данные в Bitrix: {e}")

    return redirect("client_admin_view", client_id=client.id)



@csrf_exempt
def delete_actual_payment_view(request, payment_id):
    """
    Удаляет фактический платёж и перераспределяет оставшиеся.
    """
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Только POST-запросы разрешены"})

    try:
        payment = ActualPayment.objects.get(pk=payment_id)
    except ActualPayment.DoesNotExist:
        return JsonResponse({"success": False, "error": "Платёж не найден"})

    try:
        delete_actual_payment(payment)
        return JsonResponse({"success": True})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


@csrf_exempt
@require_POST
def update_custom_payments(request, client_id):
    client = get_object_or_404(Client, pk=client_id)
    contract = Contract.objects.filter(client=client).first()
    plan = InstallmentPlan.objects.filter(contract=contract).first()

    if not plan:
        messages.error(request, "План рассрочки не найден.")
        return redirect("client_admin_view", client_id=client.id)

    total_amount_due = Decimal('0')
    errors = []

    for payment in plan.payments.all():  
        amount_field = f"amount_{payment.id}"
        status_field = f"status_{payment.id}"
        due_date_field = f"due_date_{payment.id}"

        new_amount_str = request.POST.get(amount_field)
        if new_amount_str is not None:
            try:
                new_amount = Decimal(new_amount_str)
                if new_amount < 0:
                    raise ValueError("Сумма не может быть отрицательной.")
                total_amount_due += new_amount
                payment.amount_due = new_amount
            except Exception as e:
                errors.append(f"Ошибка в платеже #{payment.number}: {e}")
        else:
            total_amount_due += payment.amount_due

        new_status = request.POST.get(status_field)
        if new_status in dict(InstallmentPayment.STATUS_CHOICES):
            payment.status = new_status
        else:
            errors.append(f"Неверный статус для платежа #{payment.number}")

        new_due_date_str = request.POST.get(due_date_field)
        if new_due_date_str:
            try:
                new_due_date = datetime.strptime(new_due_date_str, "%Y-%m-%d").date()
                payment.due_date = new_due_date
            except Exception:
                errors.append(f"Некорректная дата для платежа #{payment.number}")

        payment.save()

    expected_total = contract.total_amount - contract.discount
    if abs(total_amount_due - expected_total) > Decimal('0.01'):
        errors.append("Сумма всех платежей не равна ожидаемой сумме по договору.")

    if errors:
        for error in errors:
            messages.error(request, error)
    else:
        messages.success(request, "Платежи успешно обновлены.")

    return redirect("client_admin_view", client_id=client.id)


@csrf_exempt
def client_search_view(request):
    q = (request.GET.get('q') or '').strip().lower() 

    if q:
        results = [
            client for client in Client.objects.all()
            if (
                (client.name and q in client.name.lower()) or
                (client.surname and q in client.surname.lower()) or
                (client.middlename and q in client.middlename.lower()) or
                (client.bitrix_id and q in str(client.bitrix_id).lower())
            )
        ]
    else:
        results = Client.objects.all().order_by('surname', 'name')

    return render(request, 'client_search.html', {
        'query': q,
        'results': results
    })
    
@csrf_exempt  
@user_passes_test(lambda u: u.is_staff or u.is_superuser)
def admin_dashboard(request):
    return render(request, 'admin_dashboard.html')

@csrf_exempt
@require_POST
def add_actual_payment(request, client_id):
    client = get_object_or_404(Client, pk=client_id)
    contract = Contract.objects.filter(client=client).first()

    if not contract:
        messages.error(request, "У клиента нет контракта.")
        return redirect("client_admin_view", client_id=client.id)

    try:
        amount = Decimal(request.POST.get("amount", "0"))
        if amount <= 0:
            raise ValueError("Сумма должна быть положительной.")

        date_str = request.POST.get("date")
        if date_str:
            payment_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        else:
            payment_date = now().date()

        ActualPayment.objects.create(
            contract=contract,
            amount=amount,
            date=payment_date
        )

        messages.success(request, "Платёж успешно добавлен.")

    except Exception as e:
        messages.error(request, f"Ошибка при добавлении платежа: {e}")

    return redirect("client_admin_view", client_id=client.id)


def create_other_payment(request):
    if request.method == "POST":
        client_id = request.POST.get("client_id")
        payment_type = request.POST.get("payment_type")
        amount = request.POST.get("amount")
        comment = request.POST.get("comment")

        client = get_object_or_404(Client, id=client_id)

        other_payment = OtherPayment.objects.create(
            client=client,
            payment_type=payment_type,
            amount=amount,
            comment=comment,
            is_paid=True,                
            paid_at=timezone.now(),       
        )

        return JsonResponse({
            "status": "success",
            "message": "Прочий платёж успешно добавлен и отмечен как оплаченный!"
        })

    return JsonResponse({"status": "error", "message": "Invalid request"})


@method_decorator(csrf_exempt, name="dispatch")
class BitrixWebhookCreateClientView(View):
    
    def post(self, request):
        try:
            post_data = request.POST.dict()

            deal_data, error = get_deal_data_from_bitrix(post_data)
            if error:
                return JsonResponse({"error": error}, status=400)

            # ------ Хелперы для парсинга ------
            def safe_int(value, default=0):
                """
                Парсинг чисел из Bitrix:
                - берет часть до '|' (например "20000|RUB" -> "20000")
                - убирает незначащие пробелы и нецифровые символы (кроме разделителя дробной части)
                - возвращает int (если дробная часть есть, приводим через float -> int)
                """
                if value is None:
                    return default
                s = str(value)
                s = s.split("|")[0].strip()
                if s == "":
                    return default
                s = s.replace("\u00A0", "").replace(" ", "")
                m = re.search(r'-?\d+[\,\.\d]*', s)
                if not m:
                    try:
                        return int(s)
                    except Exception:
                        return default
                num = m.group(0).replace(',', '.')
                try:
                    return int(float(num))
                except Exception:
                    return default

            def parse_bitrix_date(value):
                """
                Парсит даты вида:
                  2025-09-01T03:00:00+03:00
                Возвращает datetime.date или None.
                """
                if not value:
                    return None
                s = str(value).strip()
                if "T" not in s and len(s) >= 10:
                    try:
                        return datetime.strptime(s[:10], "%Y-%m-%d").date()
                    except Exception:
                        pass
                try:
                    return datetime.fromisoformat(s).date()
                except Exception:
                    pass
                for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S"):
                    try:
                        return datetime.strptime(s, fmt).date()
                    except Exception:
                        continue
                return None

            # ------ Маппинг полей Bitrix -> локальные переменные ------
            # строки
            first_name = (deal_data.get("UF_CRM_1754380684375") or "").strip()
            last_name = (deal_data.get("UF_CRM_1754380678904") or "").strip()
            middlename = (deal_data.get("UF_CRM_1754380692399") or "").strip()

            # суммы / деньги (парсим через safe_int, как в старом коде)
            total_amount = safe_int(deal_data.get("OPPORTUNITY"))
            discount = safe_int(deal_data.get("UF_CRM_1742457148727"))
            bonus = safe_int(deal_data.get("UF_CRM_1742457114242"))
            first_payment = safe_int(deal_data.get("UF_CRM_1742468532579"))
            number_of_payments = safe_int(deal_data.get("UF_CRM_1742480133860"))
            preferred_payment_day = safe_int(deal_data.get("UF_CRM_1745893194511"))

            some_date = parse_bitrix_date(deal_data.get("UF_CRM_1742468566169"))

            total_with_bonus = int(max(total_amount - discount + bonus, 0))

            external_id = deal_data.get("CONTACT_ID")
            if not external_id:
                return JsonResponse({"error": "External ID (CONTACT_ID) not found in deal data"}, status=400)

            external_url = f"https://prav-buro.bitrix24.ru/rest/24/vszzr53045oedn5m/crm.contact.get.json?ID={external_id}"
            external_response = requests.get(external_url)
            if external_response.status_code != 200:
                return JsonResponse({"error": "Failed to fetch contact data from Bitrix"}, status=external_response.status_code)

            try:
                external_data = external_response.json()
            except json.JSONDecodeError:
                return JsonResponse({"error": "Invalid JSON response from Bitrix contact API"}, status=400)

            username = external_data.get("result", {}).get("PHONE", [{}])[0].get("VALUE", None)
            if not username:
                return JsonResponse({"error": "Phone number not found in Bitrix contact"}, status=400)

            current_year = datetime.now().strftime("%Y")
            password = str(russian_to_translit(last_name or "user") + current_year)

            from clients.services import ClientService
            
            # --- логика для нового поля эквайринга ---
            acquiring_value = external_data.get("result", {}).get("UF_CRM_1760099004")
            acquiring_enabled = acquiring_value == "2022"

            client, contract, plan = ClientService.create_client_with_contract(
                username=username,
                password=password,
                name=first_name,
                surname=last_name,
                middlename=middlename,
                email="client@prav-buro.ru",
                bitrix_id=str(deal_data.get("ID") or ""),
                stage="1",
                total_amount=total_with_bonus,
                discount=discount,
                first_payment=first_payment,
                first_payment_date=parse_bitrix_date(deal_data.get("UF_CRM_1742468566169")),
                number_of_payments=number_of_payments,
                preferred_payment_day=preferred_payment_day,
                
                # передаём новое поле
                acquiring_enabled=acquiring_enabled,
            )
            
            sync_client_to_bitrix(client)
            # Логи в тг, нужно в последствии добавить, думаю на проде
            text = (
                f"Новый клиент из Bitrix: {first_name} {middlename} {last_name}\n"
                f"Логин: {username}\nПароль: {password}\n"
                f"Сумма: {total_with_bonus} (сумма сделки={total_amount}, скидка={discount}, бонус={bonus})"
            )

            return JsonResponse({
                "client_id": client.id,
                "contract_id": contract.id,
                "plan_id": plan.id,
                "username": client.user.username,
                "bitrix_deal_id": deal_data.get("ID"),
                "message": "Клиент успешно создан из Bitrix24"
            })

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)
        
#AlfaAPI payments-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------  

ALFA_API_URL = "https://payment.alfabank.ru/payment/rest/register.do"
ALFA_USER_NAME = "r-prav_0-api" 
ALFA_PASSWORD = "Qwasdcvbgh243567!@"        
    


def create_payment(request, payment_id):
    payment = get_object_or_404(InstallmentPayment, id=payment_id)
    installment_plan = payment.plan

    # --- Загружаем все фактические платежи ---
    actual_payments = list(
        ActualPayment.objects.filter(plan=installment_plan).order_by("payment_date")
    )

    # Создаем копию остатков для FIFO расчёта
    remaining_actual = [p.amount for p in actual_payments]

    # --- Находим реальный amount_paid для всех платежей плана ---
    real_amount_paid = {}

    for p in installment_plan.payments.order_by("number"):
        paid = 0
        due = p.amount_due

        for i, amt in enumerate(remaining_actual):
            if amt <= 0:
                continue

            apply_sum = min(amt, due - paid)
            paid += apply_sum
            remaining_actual[i] -= apply_sum

            if paid >= due:
                break

        real_amount_paid[p.id] = paid

    amount_paid = real_amount_paid.get(payment.id, 0)
    remaining = payment.amount_due - amount_paid

    if remaining <= 0:
        messages.error(request, f"Платёж №{payment.number} уже полностью оплачен.")
        return redirect(request.META.get("HTTP_REFERER", "/"))

    amount = int(remaining * 100)
    order_number = f"InstallmentPayment-{payment.id}-{int(time.time())}"

    return_url = "https://prav-buro.ru"
    fail_url = "https://prav-buro.ru"
    description = f"Оплата по рассрочке №{payment.number} (остаток {remaining} ₽)"

    payload = {
        "userName": ALFA_USER_NAME,
        "password": ALFA_PASSWORD,
        "orderNumber": order_number,
        "amount": amount,
        "description": description,
        "returnUrl": return_url,
        "failUrl": fail_url,
    }

    try:
        response = requests.post(ALFA_API_URL, data=payload, timeout=15)
    except requests.RequestException:
        messages.error(request, "Не удалось подключиться к Альфа-Банк API.")
        return redirect(f"{return_url}?payment_status=error")

    if response.status_code != 200:
        messages.error(request, "Ошибка при обращении к Альфа-Банк API.")
        return redirect(f"{return_url}?payment_status=error")

    data = response.json()

    if data.get("errorCode") and data["errorCode"] != "0":
        messages.error(request, "Ошибка при создании платежа. Попробуйте позже.")
        return redirect(f"{return_url}?payment_status=error")

    form_url = data.get("formUrl")
    bank_order_id = data.get("orderId")

    if not form_url:
        messages.error(request, "Не удалось получить ссылку на оплату.")
        return redirect(f"{return_url}?payment_status=error")

    payment.order_id = order_number
    payment.bank_order_id = bank_order_id
    payment.save(update_fields=["order_id", "bank_order_id"])

    return redirect(form_url)
        
        
@csrf_exempt
def create_actual_payment(request):
    """
    Создаёт фактический платёж и полагается на логику внутри модели для распределения.
    POST:
      - client_id
      - amount
      - payment_date (optional, YYYY-MM-DD)
    """
    if request.method != "POST":
        return JsonResponse({"error": "Только POST запросы разрешены"}, status=405)

    try:
        client_id = request.POST.get("client_id")
        amount = request.POST.get("amount")
        payment_date = request.POST.get("payment_date")

        if not client_id or not amount:
            return JsonResponse({"error": "Необходимо передать client_id и amount"}, status=400)

        client = get_object_or_404(Client, id=client_id)
        contract = Contract.objects.filter(client=client).first()
        if not contract:
            return JsonResponse({"error": "У клиента нет контракта"}, status=400)

        plan = getattr(contract, "installmentplan", None)
        if not plan:
            return JsonResponse({"error": "У клиента нет плана рассрочки"}, status=400)

        payment = ActualPayment.objects.create(
            plan=plan,
            amount=Decimal(amount),
            payment_date=payment_date or timezone.now().date(),
        )

        return JsonResponse({
            "success": True,
            "message": f"Платёж {payment.amount} ₽ создан и попытка распределения выполнена.",
            "payment_id": payment.id,
        })

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
def payment_callback(request):
    """
    Callback от Альфа-Банка — уведомление об оплате.
    Теперь работает с новой моделью без PaymentApplication.
    """
    data = request.GET or request.POST

    order_number = data.get("orderNumber")
    status = str(data.get("status", ""))
    operation = str(data.get("operation", ""))
    amount_str = data.get("amount", "0")

    if not order_number:
        return JsonResponse({"error": "orderNumber required"}, status=400)

    if not (status == "1" and operation == "deposited"):
        return JsonResponse({
            "status": "ignored",
            "reason": f"operation={operation}, status={status}"
        }, status=200)

    # Оплата по договору с лендинга подтверждения
    contract_deal_id = _extract_contract_deal_id_from_order(order_number)
    if contract_deal_id:
        try:
            # Парсим сумму до записи комментария в таймлайн
            try:
                amount = Decimal(amount_str) / Decimal("100")
            except Exception:
                amount = Decimal("0.00")

            return _handle_contract_payment_callback(order_number, amount)
        except Exception as exc:
            return JsonResponse(
                {
                    "error": f"Failed to process contract payment callback: {exc}",
                    "orderNumber": order_number,
                    "deal_id": contract_deal_id,
                },
                status=500,
            )

    payment = InstallmentPayment.objects.filter(order_id=order_number).first()
    if not payment:
        return JsonResponse({"error": f"InstallmentPayment not found for {order_number}"}, status=404)

    # Дубликат
    if ActualPayment.objects.filter(order_id=order_number).exists():
        return JsonResponse({"status": "duplicate"}, status=200)

    # Парсим сумму
    try:
        amount = Decimal(amount_str) / Decimal("100")
    except Exception:
        amount = Decimal("0.00")

    # Создаем фактический платёж
    actual_payment = ActualPayment.objects.create(
        plan=payment.plan,
        payment_date=timezone.now().date(),
        amount=amount,
        order_id=order_number,
    )

    # --- Логирование в Telegram ---
    try:
        import telebot
        from django.conf import settings

        bot = telebot.TeleBot(BOT_TOKEN)
        chat_id = CHAT_ID

        client = payment.plan.contract.client
        fio = f"{client.name} {client.surname} {client.middlename or ''}".strip()
        date_str = timezone.now().strftime("%d.%m.%Y")

        log_message = (
            f"💳 Поступила оплата через эквайринг\n"
            f"👤 Клиент: {fio}\n"
            f"💰 Сумма: {amount} ₽\n"
            f"📅 Дата: {date_str}"
        )
        bot.send_message(chat_id, log_message)
    except Exception as e:
        print(f"[PaymentCallback] Telegram error: {e}")
    # --- конец логирования ---

    return JsonResponse({
        "status": "success",
        "actual_payment_id": actual_payment.id,
        "orderNumber": order_number,
        "amount": str(amount),
    }, status=200)
        
        
        
        
        
        
#--------------migrations-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

@method_decorator(csrf_exempt, name="dispatch")
class BitrixCreateClientFromDealView(View):
    """
    Принимает webhook от Bitrix (POST с document_id[2]), достаёт сделку через get_deal_data_from_bitrix и создаёт клиента.
    После создания — генерирует пароль и отправляет логин/пароль обратно в Битрикс.
    """

    def post(self, request):
        import json, re, requests, random, string
        from datetime import datetime
        from django.http import JsonResponse
        from django.db import transaction
        from clients.services import ClientService
        from clients.models import Client

        BITRIX_WEBHOOK = settings.BITRIX_WEBHOOK_URL.rstrip("/") + "/"

        def generate_password(length=8):
            """Генерация простого пароля"""
            chars = string.ascii_letters + string.digits
            return ''.join(random.choice(chars) for _ in range(length))

        try:
            post_data = request.POST.dict()
            if not post_data:
                try:
                    body = request.body.decode("utf-8")
                    post_data = json.loads(body)
                except Exception:
                    post_data = {}

            # --- Получаем данные сделки ---
            deal_data, error = get_deal_data_from_bitrix(post_data)
            if error:
                return JsonResponse({"error": error, "payload_keys": list(post_data.keys())}, status=400)
            if not deal_data:
                return JsonResponse({"error": "Empty deal data"}, status=400)

            # --- Хелперы ---
            def safe_int(value, default=0):
                if value is None:
                    return default
                s = str(value).split("|")[0].strip()
                s = s.replace("\u00A0", "").replace(" ", "")
                m = re.search(r"-?\d+[\,\.\d]*", s)
                if not m:
                    try:
                        return int(s)
                    except:
                        return default
                num = m.group(0).replace(",", ".")
                try:
                    return int(float(num))
                except:
                    return default

            def parse_bitrix_date(value):
                if not value:
                    return None
                s = str(value).strip()
                for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
                    try:
                        return datetime.strptime(s[:10], "%Y-%m-%d").date()
                    except:
                        continue
                try:
                    return datetime.fromisoformat(s).date()
                except:
                    return None

            def clean_text(value):
                return str(value or "").strip()

            def split_full_name(full_name):
                parts = [part for part in clean_text(full_name).split() if part]
                if len(parts) >= 2:
                    return parts[1], parts[0], " ".join(parts[2:])
                if len(parts) == 1:
                    return parts[0], "", ""
                return "", "", ""

            # --- Извлекаем данные клиента ---
            first_name = clean_text(deal_data.get("UF_CRM_1754380684375"))
            last_name = clean_text(deal_data.get("UF_CRM_1754380678904"))
            middlename = clean_text(deal_data.get("UF_CRM_1754380692399"))

            total_amount = safe_int(deal_data.get("OPPORTUNITY"))
            discount = safe_int(deal_data.get("UF_CRM_1742457148727"))
            bonus = safe_int(deal_data.get("UF_CRM_1742457114242"))
            first_payment = safe_int(deal_data.get("UF_CRM_1742468532579"))
            number_of_payments = safe_int(deal_data.get("UF_CRM_1742480133860"))
            preferred_payment_day = safe_int(deal_data.get("UF_CRM_1745893194511"))

            total_with_bonus = max(total_amount - discount + bonus, 0)

            # --- Получаем контакт ---
            external_id = deal_data.get("CONTACT_ID")
            if not external_id:
                return JsonResponse({"error": "CONTACT_ID not found"}, status=400)

            contact_url = f"https://prav-buro.bitrix24.ru/rest/24/vszzr53045oedn5m/crm.contact.get.json?ID={external_id}"
            contact_resp = requests.get(contact_url)
            if contact_resp.status_code != 200:
                return JsonResponse({"error": "Failed to fetch contact"}, status=contact_resp.status_code)

            external_data = contact_resp.json()
            contact_data = external_data.get("result") or {}
            username = external_data.get("result", {}).get("PHONE", [{}])[0].get("VALUE")
            if not username:
                return JsonResponse({"error": "Phone number not found"}, status=400)

            if not first_name:
                first_name = clean_text(contact_data.get("NAME"))
            if not last_name:
                last_name = clean_text(contact_data.get("LAST_NAME"))
            if not middlename:
                middlename = clean_text(contact_data.get("SECOND_NAME"))

            title_first_name, title_last_name, title_middlename = split_full_name(deal_data.get("TITLE"))
            if not first_name:
                first_name = title_first_name
            if not last_name:
                last_name = title_last_name
            if not middlename:
                middlename = title_middlename

            if not (first_name and last_name):
                return JsonResponse(
                    {
                        "error": "Имя и фамилия обязательны",
                        "details": "Не удалось получить имя и фамилию из полей сделки, контакта или названия сделки",
                        "deal_id": deal_data.get("ID"),
                    },
                    status=400,
                )

            # --- Генерация пароля ---
            new_password = generate_password()
            
            # --- Проверка поля 2022 ---
            acquiring_flag = (str(deal_data.get("UF_CRM_1760099004")) == "2022")

            # --- Создание клиента ---
            with transaction.atomic():
                client, contract, plan = ClientService.create_client_with_contract(
                    username=username,
                    password=new_password,
                    name=first_name,
                    surname=last_name,
                    middlename=middlename,
                    email="client@prav-buro.ru",
                    bitrix_id=str(deal_data.get("ID") or ""),
                    stage="1",
                    total_amount=total_with_bonus,
                    discount=discount,
                    first_payment=first_payment,
                    first_payment_date=parse_bitrix_date(deal_data.get("UF_CRM_1742468566169")),
                    number_of_payments=number_of_payments,
                    preferred_payment_day=preferred_payment_day,
                    acquiring_enabled=acquiring_flag,
                )

                deal_id = str(deal_data.get("ID") or "")
                bitrix_url = f"{BITRIX_WEBHOOK}crm.deal.update.json"
                auth_text = f"{username}\n{new_password}"

                payload = {
                    "id": deal_id,
                    "fields": {
                        "UF_CRM_1745888913952": auth_text,
                        **build_withdrawals_bitrix_fields(client),
                    }
                }

                response = requests.post(bitrix_url, json=payload)
                resp_data = response.json()
                if resp_data.get("error"):
                    raise Exception(f"Bitrix error: {resp_data.get('error_description', resp_data.get('error'))}")

            return JsonResponse(
                {
                    "client_id": client.id,
                    "contract_id": contract.id,
                    "plan_id": plan.id,
                    "username": client.user.username,
                    "bitrix_deal_id": deal_data.get("ID"),
                    "message": "Клиент успешно создан и данные отправлены в Битрикс",
                }
            )

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)
        


        
        
        
        
        
        
        
        
        
