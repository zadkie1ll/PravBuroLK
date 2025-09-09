from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from datetime import datetime
from dateutil.relativedelta import relativedelta
from django.contrib.auth.decorators import user_passes_test
from decimal import Decimal
from django.views.decorators.http import require_POST
from django.db import models
from django.db.models.functions import Lower
from django.db.models import Sum
from clients.models import Client
from django.utils.timezone import now
from django.db.models import Q
from .models import Contract, InstallmentPlan, InstallmentPayment, ActualPayment, OtherPayment
from django.contrib.auth.decorators import login_required
from django.db.models.functions import Cast
from django.db.models import CharField
from django.db import connection


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

@login_required
def client_admin_view(request, client_id):
    client = get_object_or_404(Client, pk=client_id)
    contract = Contract.objects.filter(client=client).first()
    plan = InstallmentPlan.objects.filter(contract=contract).first() if contract else None
    payments = plan.payments.all() if plan else []

    paid_sum = (
        plan.payments.filter(status='paid').aggregate(total=Sum('amount_due'))['total']
        if plan else 0
    )

    actual_payments = ActualPayment.objects.filter(contract=contract)
    other_payments = client.other_payments.all()
    expected_total = contract.total_amount - contract.discount if contract else 0

    # 🔥 формируем удобный список с подсчётами
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
        # обновляем данные клиента
        client.name = request.POST.get("name", client.name)
        client.surname = request.POST.get("surname", client.surname)
        client.middlename = request.POST.get("middlename", client.middlename)
        client.save()

        # обновляем контракт
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
            if publication_checked:
                total_amount += Decimal("16500")
            else:
                total_amount -= Decimal("16500")
            contract.publication = publication_checked

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

    return redirect("client_admin_view", client_id=client.id)

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
        amount_field = f"amount_{payment.id}"   # вместо payment_
        status_field = f"status_{payment.id}"

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
    
    
@user_passes_test(lambda u: u.is_staff or u.is_superuser)
def admin_dashboard(request):
    return render(request, 'admin_dashboard.html')


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