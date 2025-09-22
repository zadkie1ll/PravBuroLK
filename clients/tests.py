import sys
from decimal import Decimal
from django.test import TestCase
from clients.services import ClientService
from colorama import init, Fore, Style

init(autoreset=True)


class ClientServiceFullTests(TestCase):
    """Функциональные тесты сервиса ClientService.create_client_with_contract"""

    def _ok(self, msg: str):
        print(Fore.GREEN + "✅ " + msg)

    def _fail(self, msg: str):
        print(Fore.RED + "❌ " + msg, file=sys.stderr)

    def _create_and_check(self, test_name: str, **kwargs):
        try:
            client, contract, plan = ClientService.create_client_with_contract(**kwargs)
            payments = list(plan.payments.order_by("number"))
            total_due = sum(p.amount_due for p in payments)
            expected_total = contract.total_amount - contract.discount

            self.assertEqual(
                total_due.quantize(Decimal("0.01")),
                expected_total.quantize(Decimal("0.01"))
            )
            self._ok(f"{test_name}: OK (платежей={len(payments)}, сумма={total_due})")
        except Exception as e:
            self._fail(f"{test_name}: FAIL ({e})")
            raise

    def test_no_discount_no_first_payment(self):
        self._create_and_check(
            "Без скидки и первого платежа",
            username="u1", password="p",
            name="Иван", surname="Иванов",
            total_amount="1000.00",
            discount="0.00",
            first_payment="0.00",
            number_of_payments=4,
            preferred_payment_day=10,
        )

    def test_with_discount(self):
        self._create_and_check(
            "Со скидкой",
            username="u2", password="p",
            name="Петр", surname="Петров",
            total_amount="1000.00",
            discount="100.00",
            first_payment="0.00",
            number_of_payments=3,
            preferred_payment_day=15,
        )

    def test_with_first_payment(self):
        self._create_and_check(
            "С первым платежом",
            username="u3", password="p",
            name="Анна", surname="Сидорова",
            total_amount="1200.00",
            discount="0.00",
            first_payment="200.00",
            first_payment_date="2025-09-01",
            number_of_payments=3,
            preferred_payment_day=5,
        )

    def test_discount_and_first_payment(self):
        self._create_and_check(
            "Скидка + первый платеж",
            username="u4", password="p",
            name="Сергей", surname="Кузнецов",
            total_amount="1500.00",
            discount="200.00",
            first_payment="300.00",
            first_payment_date="2025-09-01",
            number_of_payments=4,
            preferred_payment_day=25,
        )

    def test_uneven_division(self):
        self._create_and_check(
            "Нечетное деление копеек",
            username="u5", password="p",
            name="Юлия", surname="Орлова",
            total_amount="1001.00",
            discount="0.00",
            first_payment="1.00",
            first_payment_date="2025-09-01",
            number_of_payments=3,
            preferred_payment_day=20,
        )

    def test_invalid_missing_name(self):
        test_name = "Ошибка: нет имени"
        try:
            ClientService.create_client_with_contract(
                username="u6", password="p",
                name="", surname="Фамилия",
                total_amount="1000.00",
            )
            self._fail(f"{test_name}: FAIL (ожидалось исключение)")
            self.fail("Ожидалось исключение")
        except ValueError:
            self._ok(f"{test_name}: OK (исключение поймано)")

    def test_invalid_discount_too_big(self):
        test_name = "Ошибка: скидка > сумма"
        try:
            ClientService.create_client_with_contract(
                username="u7", password="p",
                name="Мария", surname="Смирнова",
                total_amount="100.00",
                discount="80.00",
                first_payment="30.00",
            )
            self._fail(f"{test_name}: FAIL (ожидалось исключение)")
            self.fail("Ожидалось исключение")
        except ValueError:
            self._ok(f"{test_name}: OK (исключение поймано)")
