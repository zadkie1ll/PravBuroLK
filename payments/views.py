from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from datetime import datetime
from dateutil.relativedelta import relativedelta
from django.contrib.auth.decorators import user_passes_test
from decimal import Decimal
from django.urls import reverse
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.db import models
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

    # Получаем контракт клиента
    contract = Contract.objects.filter(client=client).first()

    # Рассрочка по контракту
    plan = InstallmentPlan.objects.filter(contract=contract).first() if contract else None

    # Платежи по рассрочке
    payments = plan.payments.all() if plan else []

    # Сумма уже оплаченная по рассрочке (по amount_due, т.е. что должно было быть оплачено)
    paid_sum = (
        plan.payments.filter(status='paid').aggregate(total=Sum('amount_due'))['total']
        if plan else 0
    )

    # Фактические платежи (правильно через plan__contract)
    actual_payments = ActualPayment.objects.filter(plan__contract=contract) if contract else []

    # Прочие платежи (депозиты, публикации и т.п.)
    other_payments = client.other_payments.all()

    # Сумма, которую должен оплатить клиент (с учётом скидки)
    expected_total = contract.total_amount - contract.discount if contract else 0

    # Собираем данные по каждому платежу рассрочки
    payments_data = []
    for p in payments:
        applications = p.applications.all()
        total_paid = sum(app.applied_amount for app in applications)
        payments_data.append({
            "payment": p,
            "applications": applications,
            "total_paid": total_paid,
        })

    # POST-запрос → обновление данных клиента и контракта
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
        extra_costs_checked = request.POST.get("extra_court_costs") == "on"  # новое поле

        total_amount = Decimal(request.POST.get("total_amount", "0"))
        discount = Decimal(request.POST.get("discount", "0"))
        first_payment = Decimal(request.POST.get("first_payment", "0"))
        number_of_payments = int(request.POST.get("number_of_payments", "1"))
        first_payment_date = datetime.strptime(request.POST.get("first_payment_date"), "%Y-%m-%d").date()
        second_payment_day = int(request.POST.get("second_payment_day", 15))

        base_total = contract.total_amount

        # Обновляем флаги
        if deposit_checked != contract.deposit:
            contract.deposit = deposit_checked

        if publication_checked != contract.publication:
            contract.publication = publication_checked

        if extra_costs_checked != getattr(contract, "extra_court_costs", False):
            contract.extra_court_costs = extra_costs_checked

        # Основные данные договора
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

    # === Пересчёт рассрочки ===
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

    # === После обновления рассрочки — отправляем данные в Bitrix ===
    try:
        sync_client_to_bitrix(client)
        messages.success(request, "Рассрочка пересчитана и данные успешно обновлены в Bitrix24.")
    except Exception as e:
        messages.warning(request, f"Рассрочка пересчитана, но не удалось обновить данные в Bitrix: {e}")

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
        due_date_field = f"due_date_{payment.id}"

        # --- Сумма платежа ---
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

        # --- Статус платежа ---
        new_status = request.POST.get(status_field)
        if new_status in dict(InstallmentPayment.STATUS_CHOICES):
            payment.status = new_status
        else:
            errors.append(f"Неверный статус для платежа #{payment.number}")

        # --- Дата платежа ---
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
ALFA_USER_NAME = "r-prav_0-api"      # prod логин
ALFA_PASSWORD = "Qwasdcvbgh243567!@"        # prod пароль
    


def create_payment(request, payment_id):
    payment = get_object_or_404(InstallmentPayment, id=payment_id)

    amount = int(float(payment.amount_due) * 100)
    order_number = f"{payment.__class__.__name__}-{payment.id}-{int(time.time())}"

    return_url = "http://217.149.31.38/"
    fail_url = "http://217.149.31.38/"
    description = f"Оплата по рассрочке №{payment.number}"

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
        print("Альфа-Банк ответил:", response.status_code, response.text)
    except requests.RequestException as e:
        print("Ошибка соединения с Альфа-Банк API:", e)
        return redirect(f"{return_url}?payment_status=error")

    if response.status_code != 200:
        print("Ошибка HTTP:", response.status_code, response.text)
        return redirect(f"{return_url}?payment_status=error")

    data = response.json()
    print("Ответ JSON от Альфа-Банка:", data)

    if data.get("errorCode") and data["errorCode"] != "0":
        print("Ошибка при создании платежа:", data)
        return redirect(f"{return_url}?payment_status=error")

    form_url = data.get("formUrl")
    order_id = data.get("orderId")

    if not form_url:
        print("Не удалось получить ссылку на оплату:", data)
        return redirect(f"{return_url}?payment_status=error")

    payment.order_id = order_id
    payment.save(update_fields=["order_id"])

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
    Callback от Альфа-Банка — уведомление об оплате
    """
    data = request.POST or request.GET
    order_id = data.get("orderId")
    order_status = str(data.get("orderStatus", ""))
    error_code = str(data.get("errorCode", ""))

    if not order_id:
        return JsonResponse({"error": "orderId required"}, status=400)

    if ActualPayment.objects.filter(order_id=order_id).exists():
        return JsonResponse({"status": "duplicate"}, status=200)

    if error_code != "0" or order_status != "2":
        return JsonResponse({
            "status": "not paid",
            "orderStatus": order_status,
            "errorCode": error_code,
        }, status=200)

    payment = InstallmentPayment.objects.filter(order_id=order_id).first()
    if not payment:
        return JsonResponse({"error": "payment not found"}, status=404)

    if payment.status == "paid":
        return JsonResponse({"status": "already paid"}, status=200)

    actual_payment = ActualPayment.objects.create(
        plan=payment.plan,
        payment_date=timezone.now().date(),
        amount=payment.amount_due,
        order_id=order_id,
    )

    payment.refresh_from_db()

    return JsonResponse({
        "status": "success",
        "payment_id": payment.id,
        "actual_payment_id": actual_payment.id,
        "amount_paid": str(payment.amount_paid),
        "order_id": order_id,
    })
        
        
        
        
        
        
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

        BITRIX_WEBHOOK = "https://prav-buro.bitrix24.ru/rest/24/pa1x5irnfpbcnh27/"

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

            # --- Извлекаем данные клиента ---
            first_name = (deal_data.get("UF_CRM_1754380684375") or "").strip()
            last_name = (deal_data.get("UF_CRM_1754380678904") or "").strip()
            middlename = (deal_data.get("UF_CRM_1754380692399") or "").strip()

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
            username = external_data.get("result", {}).get("PHONE", [{}])[0].get("VALUE")
            if not username:
                return JsonResponse({"error": "Phone number not found"}, status=400)

            # --- Генерация пароля ---
            new_password = generate_password()

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
                )

                deal_id = str(deal_data.get("ID") or "")
                bitrix_url = f"{BITRIX_WEBHOOK}crm.deal.update.json"
                auth_text = f"{username}\n{new_password}"

                payload = {
                    "id": deal_id,
                    "fields": {
                        "UF_CRM_1745888913952": auth_text  
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
        
        
        
        
        
        
        
        
        
        
        
        
#TEMP LOGS-----------------------------------------------------------


# payments/debug_views.py
import json
import threading
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

# потокобезопасный lock для записи в файл
_log_lock = threading.Lock()

# Путь к файлу лога — можно переопределить в settings.ALFA_CALLBACK_LOG_PATH
DEFAULT_LOG_PATH = Path(getattr(settings, "ALFA_CALLBACK_LOG_PATH", settings.BASE_DIR)) / "alfa_callbacks.log"


def _ensure_log_path(path: Path):
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)


def _pretty_json(obj):
    try:
        return json.dumps(obj, ensure_ascii=False, indent=2)
    except Exception:
        return str(obj)


@csrf_exempt
def payment_callback_debug(request):
    """
    Временный хендлер для тестирования: записывает тела всех входящих запросов в текстовый файл.
    Формат записи:
    === [TIMESTAMP] ===
    Remote IP: ...
    Method: POST
    Path: /api/alfa/payment-callback/
    --- HEADERS ---
    { ... }
    --- QUERY / GET ---
    { ... }
    --- FORM ---
    { ... }
    --- JSON BODY ---
    { ... }
    --- RAW BODY ---
    <raw body as decoded utf-8 with replacement>
    === END ===

    Возвращает {"status": "logged"} чтобы внешняя система (банк) видела 200.
    """
    log_path = Path(getattr(settings, "ALFA_CALLBACK_LOG_PATH", DEFAULT_LOG_PATH))
    _ensure_log_path(log_path)

    # Сбор данных
    timestamp = datetime.utcnow().isoformat(timespec="seconds") + "Z"  # UTC timestamp
    remote_addr = request.META.get("REMOTE_ADDR", "unknown")
    method = request.method
    path = request.get_full_path()

    # Заголовки
    try:
        headers = {k: v for k, v in request.headers.items()}
    except Exception:
        # Старые версии Django могут не иметь request.headers
        headers = {}
        for k, v in request.META.items():
            if k.startswith("HTTP_"):
                headers[k[5:].replace("_", "-").title()] = v

    # Query params
    query_params = dict(request.GET)

    # Form data (POST form-encoded / multipart)
    form_params = dict(request.POST)

    # Raw body (попытка декодировать)
    try:
        raw_body = request.body.decode("utf-8")
    except Exception:
        raw_body = request.body.decode("utf-8", errors="replace")

    # JSON body (если возможно)
    json_body = None
    if raw_body:
        try:
            json_body = json.loads(raw_body)
        except Exception:
            json_body = None

    # Собираем красивую запись
    sep = "\n" + ("=" * 80) + "\n"
    parts = [
        sep,
        f"[{timestamp}]\n",
        f"Remote IP: {remote_addr}\n",
        f"Method: {method}\n",
        f"Path: {path}\n\n",
        "--- HEADERS ---\n",
        _pretty_json(headers) + "\n\n",
        "--- QUERY / GET ---\n",
        _pretty_json(query_params) + "\n\n",
        "--- FORM (POST) ---\n",
        _pretty_json(form_params) + "\n\n",
        "--- JSON BODY (parsed) ---\n",
        (_pretty_json(json_body) if json_body is not None else "null") + "\n\n",
        "--- RAW BODY (utf-8, errors=replacement) ---\n",
        raw_body + "\n\n",
        "--- META (selected) ---\n",
        _pretty_json({
            "CONTENT_TYPE": request.META.get("CONTENT_TYPE"),
            "CONTENT_LENGTH": request.META.get("CONTENT_LENGTH"),
            "HTTP_USER_AGENT": request.META.get("HTTP_USER_AGENT"),
            "HTTP_HOST": request.META.get("HTTP_HOST"),
        }) + "\n",
        ("=" * 80) + "\n\n",
    ]

    entry = "".join(parts)

    # Запись в файл с блокировкой
    try:
        with _log_lock:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(entry)
                f.flush()
    except Exception as e:
        # Если лог записать не удалось — возвращаем ошибку 500, но для webhook теста можно вернуть 200.
        return JsonResponse({"status": "log_error", "error": str(e)}, status=500)

    # Вернём 200, чтобы внешняя система считала callback доставленным.
    return JsonResponse({"status": "logged"})