from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from datetime import datetime
from dateutil.relativedelta import relativedelta
from django.contrib.auth.decorators import user_passes_test
from decimal import Decimal
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.db import models
from django.db.models.functions import Lower
from django.db.models import Sum
from django.views import View
import time
from clients.models import Client
import requests
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
from .utilities import get_deal_data_from_bitrix, russian_to_translit

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

@csrf_exempt
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
                # если приходит уже просто yyyy-mm-dd
                if "T" not in s and len(s) >= 10:
                    try:
                        return datetime.strptime(s[:10], "%Y-%m-%d").date()
                    except Exception:
                        pass
                # попытка через fromisoformat (поддерживает +03:00)
                try:
                    return datetime.fromisoformat(s).date()
                except Exception:
                    pass
                # fallback на явные форматы
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

            # пример поля-даты из Bitrix (пример, который вы прислали)
            some_date = parse_bitrix_date(deal_data.get("UF_CRM_1742468566169"))
            # если нужно, можете логировать или передавать some_date в сервис (см. комментарий ниже)

            # ------ Бизнес-логика суммы: скидка вычитается, бонус прибавляется ------
            # (интеллигентно, чтобы не уйти в отрицательное значение)
            total_with_bonus = int(max(total_amount - discount + bonus, 0))

            # Генерация уникальных логина/пароля (как в вашем примере)
            # --- Получаем контакт (для логина используем телефон) ---
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

            # --- Генерация пароля: фамилия (транслитом) + текущий год ---
            current_year = datetime.now().strftime("%Y")
            password = str(russian_to_translit(last_name or "user") + current_year)

            # ------ Передаем подготовленные значения в инкапсулированный сервис ------
            # Обратите внимание: передаем те же параметры, что и раньше, но уже с распарсенными значениями.
            from clients.services import ClientService
            
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
            )

            # ---- (опционально) лог в Telegram как в старом коде ----
            text = (
                f"Новый клиент из Bitrix: {first_name} {middlename} {last_name}\n"
                f"Логин: {username}\nПароль: {password}\n"
                f"Сумма: {total_with_bonus} (сумма сделки={total_amount}, скидка={discount}, бонус={bonus})"
            )
            # Telegram_log(text)

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