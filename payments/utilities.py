#utils_for_all_views
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import JsonResponse
import json
import os
import re
from django.utils import timezone
from django.db import models
from datetime import datetime, timedelta
import requests  
from payments.models import ActualPayment, PaymentApplication, InstallmentPlan

BITRIX_WEBHOOK_URL = "https://prav-buro.bitrix24.ru/rest/24/pa1x5irnfpbcnh27/"

def get_deal_data_from_bitrix(post_data):
    """
    Извлекает ID сделки из POST-данных Bitrix24 и возвращает данные сделки
    """
    document_id_2 = post_data.get('document_id[2]')
    if not document_id_2:
        return None, 'document_id[2] not found'

    deal_id_match = re.search(r'DEAL_(\d+)', document_id_2)
    if not deal_id_match:
        return None, 'Invalid deal ID format'

    deal_id = deal_id_match.group(1)

    # Подставь актуальный вебхук и пользователя
    webhook_url = f"{BITRIX_WEBHOOK_URL}crm.deal.get.json?ID={deal_id}"
    # print(webhook_url)
    response = requests.get(webhook_url)

    if response.status_code != 200:
        return None, f"Bitrix24 request failed with status {response.status_code}"

    try:
        deal_data = response.json().get('result', {})
        return deal_data, None
    except json.JSONDecodeError:
        return None, 'Invalid JSON response from Bitrix'
    
    
def russian_to_translit(text):
    translit_dict = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 
        'е': 'e', 'ё': 'yo', 'ж': 'zh', 'з': 'z', 'и': 'i', 
        'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n', 
        'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 
        'у': 'u', 'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 
        'ш': 'sh', 'щ': 'shch', 'ъ': '', 'ы': 'y', 'ь': '', 
        'э': 'e', 'ю': 'yu', 'я': 'ya',
        'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'G', 'Д': 'D', 
        'Е': 'E', 'Ё': 'Yo', 'Ж': 'Zh', 'З': 'Z', 'И': 'I', 
        'Й': 'Y', 'К': 'K', 'Л': 'L', 'М': 'M', 'Н': 'N', 
        'О': 'O', 'П': 'P', 'Р': 'R', 'С': 'S', 'Т': 'T', 
        'У': 'U', 'Ф': 'F', 'Х': 'Kh', 'Ц': 'Ts', 'Ч': 'Ch', 
        'Ш': 'Sh', 'Щ': 'Shch', 'Ъ': '', 'Ы': 'Y', 'Ь': '', 
        'Э': 'E', 'Ю': 'Yu', 'Я': 'Ya'
    }
    translit_text = ''.join(translit_dict.get(char, char) for char in text)
    return translit_text


















from decimal import Decimal
from django.db import transaction, models
from django.utils import timezone
from payments.models import ActualPayment, PaymentApplication, InstallmentPlan

def replace_actual_payment(old_payment_id, new_amount, new_date=None):
    """
    Удаляет старый платёж и создаёт новый исправленный,
    с повторным распределением по плану.
    """
    with transaction.atomic():
        try:
            old_payment = ActualPayment.objects.select_related('plan__contract__client').get(pk=old_payment_id)
        except ActualPayment.DoesNotExist:
            raise ValueError(f"Платёж с ID {old_payment_id} не найден")

        plan = old_payment.plan

        # Удаляем все связи PaymentApplication
        PaymentApplication.objects.filter(actual_payment=old_payment).delete()

        # Откатываем суммы в InstallmentPayment
        for inst_payment in plan.payments.all():
            total_applied = inst_payment.applications.aggregate(total=models.Sum('applied_amount'))['total'] or Decimal('0.00')
            inst_payment.amount_paid = total_applied
            if inst_payment.amount_paid >= inst_payment.amount_due:
                inst_payment.status = 'paid'
            elif inst_payment.amount_paid > 0:
                inst_payment.status = 'partial'
            else:
                inst_payment.status = 'pending'
            inst_payment.save()

        # Удаляем старый платеж
        old_payment.delete()

        # Создаём новый платёж
        new_payment = ActualPayment(
            plan=plan,
            amount=Decimal(new_amount),
            payment_date=new_date or timezone.now().date(),
            is_applied=False
        )
        new_payment._skip_apply = True  # флаг для отключения авто-apply при save
        new_payment.save()  # обычное save, без update_fields
        new_payment.apply_payment()  # распределяем платеж

        return new_payment


def recalc_plan(plan: InstallmentPlan):
    """
    Полностью пересчитывает план рассрочки:
    удаляет старые связи и заново распределяет фактические платежи.
    """
    with transaction.atomic():
        PaymentApplication.objects.filter(payment__plan=plan).delete()

        plan.payments.update(amount_paid=Decimal("0.00"), status="pending")

        actuals = list(plan.actual_payments.select_for_update().order_by("payment_date", "created_at", "id"))

        for act in actuals:
            act._skip_apply = True
            act.is_applied = False
            act.save()  # обычное save

        for act in actuals:
            act.apply_payment()

        for inst in plan.payments.select_for_update():
            total = PaymentApplication.objects.filter(payment=inst).aggregate(sum=models.Sum("applied_amount"))["sum"] or Decimal("0.00")
            inst.amount_paid = total
            inst.status = "paid" if total >= inst.amount_due else "partial" if total > 0 else "pending"
            inst.save()


def delete_actual_payment(payment: ActualPayment):
    """
    Удаляет фактический платёж и пересчитывает план.
    """
    if not payment.plan:
        raise ValueError("Фактический платёж не привязан к плану")

    plan = payment.plan

    with transaction.atomic():
        PaymentApplication.objects.filter(actual_payment=payment).delete()
        payment.delete()

    recalc_plan(plan)


def recreate_actual_payment(payment: ActualPayment, new_amount, new_date=None) -> ActualPayment:
    """
    Пересоздаёт фактический платёж с новой суммой и датой,
    полностью пересчитывает план.
    """
    if not payment.plan:
        raise ValueError("Фактический платёж не привязан к плану")

    plan = payment.plan

    with transaction.atomic():
        PaymentApplication.objects.filter(actual_payment=payment).delete()
        payment.delete()

        new_payment = ActualPayment(
            plan=plan,
            amount=Decimal(new_amount),
            payment_date=new_date or timezone.now().date(),
            is_applied=False
        )
        new_payment._skip_apply = True
        new_payment.save()
        new_payment.apply_payment()

    recalc_plan(plan)
    return new_payment