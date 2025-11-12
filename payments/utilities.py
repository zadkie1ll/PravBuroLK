from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import JsonResponse
import json
import os
import re
from django.utils import timezone
from django.db import models
from datetime import datetime, timedelta
import requests  # заменяем httpx на requests


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
from django.db import transaction
from django.utils import timezone
from payments.models import ActualPayment, PaymentApplication

def replace_actual_payment(old_payment_id, new_amount, new_date=None):
    """
    Удаляет старый платёж и создаёт новый исправленный, 
    с повторным распределением по плану.

    Args:
        old_payment_id (int): ID старого ActualPayment
        new_amount (Decimal): новая сумма платежа
        new_date (date, optional): дата платежа (по умолчанию старая)
    """
    from payments.models import ActualPayment  # чтобы избежать циклов импорта

    with transaction.atomic():
        try:
            old_payment = ActualPayment.objects.select_related('plan__contract__client').get(pk=old_payment_id)
        except ActualPayment.DoesNotExist:
            raise ValueError(f"Платёж с ID {old_payment_id} не найден")

        plan = old_payment.plan
        client = getattr(plan.contract, 'client', None)

        # 1️⃣ — Удаляем все связи PaymentApplication
        PaymentApplication.objects.filter(actual_payment=old_payment).delete()

        # 2️⃣ — Откатываем суммы в InstallmentPayment (amount_paid)
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

        # 3️⃣ — Удаляем старый ActualPayment
        old_payment.delete()

        # 4️⃣ — Создаём новый платёж
        new_payment = ActualPayment.objects.create(
            plan=plan,
            amount=Decimal(new_amount),
            payment_date=new_date or timezone.now().date(),
            order_id=None,  # можно оставить None, если не важно
            is_applied=False
        )

        # 5️⃣ — Автоматически применяем новый платёж (распределяем)
        new_payment.apply_payment()

        print(f"[replace_actual_payment] Старый платёж #{old_payment_id} заменён на новый #{new_payment.id}")

        # 6️⃣ — Возвращаем объект нового платежа
        return new_payment
    
    
    
    
    
    
    
    
    
def recreate_actual_payment(payment: ActualPayment, new_amount, new_date=None) -> ActualPayment:
    """
    Пересоздаёт фактический платёж с новой суммой и датой.
    Полностью перераспределяет все фактические платежи по плану.
    Всё выполняется в одной атомарной транзакции.
    """

    if not payment.plan:
        raise ValueError("У платежа нет связанного плана")

    plan = payment.plan
    print(f"[recreate_actual_payment] Старт перерасчёта для плана #{plan.id}")

    with transaction.atomic():
        # --- 1. Удаляем все PaymentApplication, связанные с планом
        deleted_apps = PaymentApplication.objects.filter(payment__plan=plan).delete()
        print(f"[recreate_actual_payment] Удалено {deleted_apps[0]} PaymentApplication")

        # --- 2. Сбрасываем платежи рассрочки
        updated = plan.payments.update(amount_paid=Decimal("0.00"), status="pending")
        print(f"[recreate_actual_payment] Сброшено {updated} платежей рассрочки")

        # --- 3. Удаляем старый фактический платёж
        old_id = payment.id
        payment.delete()
        print(f"[recreate_actual_payment] Старый платёж #{old_id} удалён")

        # --- 4. Создаём новый фактический платёж без автоприменения
        new_payment = ActualPayment(
            plan=plan,
            amount=Decimal(new_amount),
            payment_date=new_date or timezone.now().date(),
            is_applied=False
        )
        new_payment._skip_apply = True  # ⛔️ отключаем авто-apply в save()
        new_payment.save()
        print(f"[recreate_actual_payment] Новый платёж #{new_payment.id} создан (без автоприменения)")

        # --- 5. Применяем все фактические платежи в порядке даты
        actuals = list(plan.actual_payments.order_by("payment_date", "id"))
        print(f"[recreate_actual_payment] Найдено {len(actuals)} фактических платежей для перераспределения")

        for act_payment in actuals:
            try:
                # Сбрасываем флаг, чтобы гарантировать повторное применение
                ActualPayment.objects.filter(pk=act_payment.pk).update(is_applied=False)
                act_payment.is_applied = False
                act_payment.apply_payment()
                print(f"[recreate_actual_payment] Платёж #{act_payment.id} успешно перераспределён")
            except Exception as e:
                print(f"[recreate_actual_payment] Ошибка при перераспределении платежа #{act_payment.id}: {e}")

    print(f"[recreate_actual_payment] Перераспределение завершено. Новый платёж #{new_payment.id}")
    return new_payment
