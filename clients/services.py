"""
Service layer для создания Client + Contract + InstallmentPlan и management-команда для импорта

Файл предлагается поместить в приложение `clients`:
- clients/services.py  (основной код сервиса)
- clients/management/commands/import_clients.py  (management команда импорта)
- clients/tests/test_service.py  (юнит-тесты для сервиса)

Код максимально универсален: использует django.apps.apps.get_model чтобы корректно работать при разнесённых приложениях.
"""

from __future__ import annotations
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
from datetime import date, datetime
import calendar
import logging
from payments.views import calculate_payments
from typing import Optional, Tuple, Dict, Any
from clients.models import Client
from payments.models import Contract, InstallmentPlan, InstallmentPayment
from django.db import transaction
from django.utils import timezone
from django.contrib.auth.models import User
from django.apps import apps

logger = logging.getLogger(__name__)

# --- Вспомогательные функции -------------------------------------------------

def _ensure_username(desired: Optional[str]) -> str:
    """Гарантируем уникальный username. Если желаемый уже занят — добавляем числовой суффикс."""
    base = desired or f"user_{int(timezone.now().timestamp())}"
    candidate = base
    suffix = 0
    while User.objects.filter(username=candidate).exists():
        suffix += 1
        candidate = f"{base}{suffix}"
    return candidate


def _parse_date(value: Optional[Any]) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    # ожидаем формат 'YYYY-MM-DD' наиболее часто
    if isinstance(value, str):
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except Exception:
            try:
                # более гибкий парсер, если установлен python-dateutil
                from dateutil.parser import parse
                return parse(value).date()
            except Exception:
                raise ValueError(f"Невозможно распарсить дату: {value}")
    raise ValueError(f"Неподдерживаемый тип для даты: {type(value)}")


def _to_decimal(value: Any) -> Decimal:
    if value is None:
        return Decimal('0.00')
    if isinstance(value, Decimal):
        return value.quantize(Decimal('0.01'))
    # Преобразуем через строку, чтобы избежать ошибок с float
    return Decimal(str(value)).quantize(Decimal('0.01'))


def add_months(origin: date, months: int) -> date:
    """Добавляем months месяцев к origin корректно учитывая года и длину месяца."""
    year = origin.year + (origin.month - 1 + months) // 12
    month = (origin.month - 1 + months) % 12 + 1
    day = min(origin.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


# --- Сервисный слой ---------------------------------------------------------

class ClientService:
    """Сервис-инкапсуляция всей логики создания клиента + договора + плана рассрочки.

    Использование:
        client, contract, plan = ClientService.create_client_with_contract(**kwargs)
    """

    @staticmethod
    @transaction.atomic
    def create_client_with_contract(
        username: str,
        password: Optional[str],
        name: str,
        surname: str,
        middlename: Optional[str] = None,
        email: Optional[str] = None,
        bitrix_id: Optional[str] = None,
        stage: Optional[Any] = None,
        # параметры договора
        total_amount: Any = None,
        discount: Any = 0,
        first_payment: Any = 0,
        first_payment_date: Optional[Any] = None,
        number_of_payments: int = 1,
        preferred_payment_day: int = 15,
        extra_fields: Optional[Dict[str, Any]] = None,
    ) -> Tuple["Client", "Contract", "InstallmentPlan"]:
        """Создаёт User -> Client -> Contract -> InstallmentPlan -> InstallmentPayment'ы.

        Валидирует входные данные и использует transaction.atomic: либо всё создаётся, либо откат.
        """
        apps.get_model  # для подсказки типа в IDE

        Client = apps.get_model('clients', 'Client')
        Contract = apps.get_model('payments', 'Contract')
        InstallmentPlan = apps.get_model('payments', 'InstallmentPlan')
        InstallmentPayment = apps.get_model('payments', 'InstallmentPayment')

        # --- базовые проверки -------------------------------------------------
        if not (name and surname):
            raise ValueError("Имя и фамилия обязательны")
        if total_amount is None:
            raise ValueError("total_amount обязателен")

        total_amount_d = _to_decimal(total_amount)
        discount_d = _to_decimal(discount)
        first_payment_d = _to_decimal(first_payment)

        if first_payment_d + discount_d > total_amount_d:
            raise ValueError("Сумма скидки + первый платёж не может превышать общую сумму")

        first_payment_date_parsed = _parse_date(first_payment_date) or date.today()

        # --- User -------------------------------------------------------------
        username_unique = _ensure_username(username)
        if not password:
            # безопасная автогенерация простым способом (можно заменить на полноценную генерацию)
            password = User.objects.make_random_password()

        user = User.objects.create_user(
            username=username_unique,
            password=password,
            first_name=name,
            last_name=surname,
            email=email or "",
        )

        # --- Client -----------------------------------------------------------
        client_kwargs = {
            'user': user,
            'name': name,
            'surname': surname,
            'middlename': middlename,
            'bitrix_id': bitrix_id,
        }
        if stage is not None:
            # stage может быть id, имя или экземпляр модели
            StageTemplate = apps.get_model('clients', 'StageTemplate')
            if isinstance(stage, StageTemplate):
                client_kwargs['stage'] = stage
            else:
                # попробуем найти по id или по имени
                try:
                    client_kwargs['stage'] = StageTemplate.objects.get(pk=stage)
                except Exception:
                    try:
                        client_kwargs['stage'] = StageTemplate.objects.get(name=stage)
                    except Exception:
                        client_kwargs['stage'] = None

        client = Client.objects.create(**{k: v for k, v in client_kwargs.items() if v is not None})

        # --- Contract ---------------------------------------------------------
        contract = Contract.objects.create(
            client=client,
            total_amount=total_amount_d,
            discount=discount_d,
            first_payment=first_payment_d,
            first_payment_date=first_payment_date_parsed,
            number_of_payments=number_of_payments,
            preferred_payment_day=preferred_payment_day,
        )

        # --- Plan и расчёт платежей ------------------------------------------
        plan = InstallmentPlan.objects.create(contract=contract)

        # === Первый платёж фиксируем отдельно ===
        if first_payment_d > 0:
            InstallmentPayment.objects.create(
                plan=plan,
                number=1,
                due_date=first_payment_date_parsed,
                amount_due=first_payment_d,
                status="paid",   # или is_paid=True — зависит от твоей модели
            )

        # оставшаяся сумма после скидки и первого платежа
        remaining = total_amount_d - discount_d - first_payment_d

        # базовая часть каждого платежа (с округлением вниз)
        monthly_base = (remaining / Decimal(number_of_payments)).quantize(
            Decimal('0.01'), rounding=ROUND_DOWN
        )

        remainder = (remaining - (monthly_base * number_of_payments)).quantize(
            Decimal('0.01')
        )
        remainder_cents = int(
            (remainder * 100).to_integral_value(rounding=ROUND_HALF_UP)
        )

        for i in range(1, number_of_payments + 1):
            extra_cent = Decimal('0.01') if i <= remainder_cents else Decimal('0.00')
            amount_due = (monthly_base + extra_cent).quantize(Decimal('0.01'))

            due_base = add_months(first_payment_date_parsed, i)
            last_day = calendar.monthrange(due_base.year, due_base.month)[1]
            due_day = min(preferred_payment_day, last_day)
            due_date = due_base.replace(day=due_day)

            InstallmentPayment.objects.create(
                plan=plan,
                number=i + 1 if first_payment_d > 0 else i,  # смещаем нумерацию
                due_date=due_date,
                amount_due=amount_due,
            )

        plan.calculated = True
        plan.save()

        return client, contract, plan


# --- Management команда: пример импорта ------------------------------------
# Поместите как clients/management/commands/import_clients.py

import json
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = 'Импорт клиентов из JSON для новой системы (вызов ClientService).'

    def add_arguments(self, parser):
        parser.add_argument('--source', type=str, required=True, help='Путь к файлу JSON или URL с файлом')
        parser.add_argument('--dry-run', action='store_true', help='Не сохранять в БД, только вывод')

    def handle(self, *args, **options):
        source = options['source']
        dry = options['dry_run']

        # Поддержка локального файла
        if source.startswith('http://') or source.startswith('https://'):
            try:
                import requests
                resp = requests.get(source)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                self.stderr.write(f"Ошибка при запросе {source}: {e}")
                return
        else:
            with open(source, 'r', encoding='utf-8') as fh:
                data = json.load(fh)

        created = 0
        errors = 0
        for idx, item in enumerate(data if isinstance(data, list) else [data]):
            try:
                # Пример маппинга — отнаследуй под свою структуру старого ЛК
                service_kwargs = {
                    'username': item.get('username') or item.get('login') or f"imp_{idx}",
                    'password': item.get('password'),
                    'name': item.get('first_name') or item.get('name'),
                    'surname': item.get('last_name') or item.get('surname'),
                    'middlename': item.get('middlename'),
                    'email': item.get('email'),
                    'bitrix_id': item.get('bitrix_id'),
                    'total_amount': item.get('contract', {}).get('total_amount') if item.get('contract') else item.get('total_amount'),
                    'discount': item.get('contract', {}).get('discount', 0),
                    'first_payment': item.get('contract', {}).get('first_payment', 0),
                    'first_payment_date': item.get('contract', {}).get('first_payment_date'),
                    'number_of_payments': item.get('contract', {}).get('number_of_payments', 1),
                    'preferred_payment_day': item.get('contract', {}).get('preferred_payment_day', 15),
                }

                if dry:
                    self.stdout.write(f"[DRY] would create client: {service_kwargs}")
                else:
                    client, contract, plan = ClientService.create_client_with_contract(**service_kwargs)
                    created += 1
                    self.stdout.write(f"Created client {client.id} contract {contract.id}")
            except Exception as e:
                errors += 1
                self.stderr.write(f"Ошибка для записи {idx}: {e}")

        self.stdout.write(f"Готово. Создано: {created}. Ошибок: {errors}.")


# --- Тесты: clients/tests/test_service.py ---------------------------------
# Небольшой набор тестов, который поможет проверить корректность распределения сумм

from django.test import TestCase

class ClientServiceTests(TestCase):
    def test_create_client_and_plan_distributes_cents(self):
        # создаём с суммой, не делящейся на число платежей
        data = {
            'username': 'testuser_svc',
            'password': 'pass',
            'name': 'Тест',
            'surname': 'Тестов',
            'total_amount': '1000.00',
            'discount': '0.00',
            'first_payment': '1.00',
            'first_payment_date': '2025-09-01',
            'number_of_payments': 3,
            'preferred_payment_day': 5,
        }
        client, contract, plan = ClientService.create_client_with_contract(**data)
        payments = plan.payments.order_by('number')
        self.assertEqual(payments.count(), 3)
        # сумма всех платежей + первый платёж + скидка == total_amount
        total_due = sum([p.amount_due for p in payments]) + contract.first_payment + contract.discount
        self.assertEqual(total_due.quantize(Decimal('0.01')), contract.total_amount.quantize(Decimal('0.01')))

    def test_username_collision_resolved(self):
        # создаём два пользователя с одним желаемым username
        u1_kwargs = {
            'username': 'collision_user',
            'password': 'p',
            'name': 'A',
            'surname': 'B',
            'total_amount': '10',
        }
        client1, *_ = ClientService.create_client_with_contract(**u1_kwargs)
        client2, *_ = ClientService.create_client_with_contract(**u1_kwargs)
        self.assertNotEqual(client1.user.username, client2.user.username)
