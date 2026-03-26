import sys
from decimal import Decimal
from unittest.mock import Mock, patch
from django.contrib.auth.models import User
from django.test import TestCase
from django.test import SimpleTestCase, override_settings
from django.core.cache import cache
from django.urls import reverse
from clients.models import Client
from clients.services import ClientService
from clients.lawyer_info import get_client_lawyer_info
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


@override_settings(
    MEGAFON_VATS_WEBHOOK_URL="https://megafon.test/webhook",
    LAWYER_INFO_CACHE_TTL=60,
)
class ClientLawyerInfoTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    @patch("clients.lawyer_info.requests.post")
    @patch("clients.lawyer_info.requests.get")
    def test_get_client_lawyer_info_merges_bitrix_and_megafon_data(self, mock_get, mock_post):
        deal_response = Mock()
        deal_response.raise_for_status.return_value = None
        deal_response.json.return_value = {"result": {"ASSIGNED_BY_ID": "24"}}

        user_response = Mock()
        user_response.raise_for_status.return_value = None
        user_response.json.return_value = {
            "result": [
                {
                    "NAME": "Иван",
                    "LAST_NAME": "Иванов",
                    "EMAIL": "ivanov@example.com",
                    "SECOND_NAME": "",
                    "PERSONAL_PHOTO": "",
                }
            ]
        }
        mock_get.side_effect = [deal_response, user_response]

        megafon_response = Mock()
        megafon_response.raise_for_status.return_value = None
        megafon_response.json.return_value = {
            "result": [
                {
                    "first_name": "Иван",
                    "last_name": "Иванов",
                    "phone": "+79990001122",
                    "otchestvo": "https://img.example.com/avatar.jpg",
                }
            ]
        }
        mock_post.return_value = megafon_response

        data = get_client_lawyer_info("1001")

        self.assertEqual(data["first_name"], "Иван")
        self.assertEqual(data["last_name"], "Иванов")
        self.assertEqual(data["email"], "ivanov@example.com")
        self.assertEqual(data["phone"], "+79990001122")
        self.assertEqual(data["avatar_url"], "https://img.example.com/avatar.jpg")

    @patch("clients.lawyer_info.requests.post")
    @patch("clients.lawyer_info.requests.get")
    def test_get_client_lawyer_info_uses_cache(self, mock_get, mock_post):
        deal_response = Mock()
        deal_response.raise_for_status.return_value = None
        deal_response.json.return_value = {"result": {"ASSIGNED_BY_ID": "99"}}

        user_response = Mock()
        user_response.raise_for_status.return_value = None
        user_response.json.return_value = {
            "result": [
                {
                    "NAME": "Анна",
                    "LAST_NAME": "Смирнова",
                    "EMAIL": "anna@example.com",
                }
            ]
        }
        mock_get.side_effect = [deal_response, user_response]

        megafon_response = Mock()
        megafon_response.raise_for_status.return_value = None
        megafon_response.json.return_value = {"result": []}
        mock_post.return_value = megafon_response

        first = get_client_lawyer_info("2002")
        second = get_client_lawyer_info("2002")

        self.assertEqual(first, second)
        self.assertEqual(mock_get.call_count, 2)


class SetIsBlockedTests(TestCase):
    @patch("clients.views.requests.post")
    def test_set_is_blocked_updates_client_from_bitrix_field(self, mock_post):
        user = User.objects.create_user(username="blocked-user", password="pwd")
        client = Client.objects.create(
            user=user,
            name="Ivan",
            surname="Ivanov",
            bitrix_id="12345",
            isBlocked=False,
        )

        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "result": {
                "UF_CRM_1772457154217": 1,
            }
        }
        mock_post.return_value = response

        result = self.client.post(
            reverse("set_is_blocked"),
            {"document_id[2]": "12345"},
        )

        client.refresh_from_db()

        self.assertEqual(result.status_code, 200)
        self.assertTrue(client.isBlocked)

    @patch("clients.views.requests.post")
    def test_set_is_blocked_accepts_deal_prefixed_document_id(self, mock_post):
        user = User.objects.create_user(username="blocked-user-2", password="pwd")
        client = Client.objects.create(
            user=user,
            name="Petr",
            surname="Petrov",
            bitrix_id="12345",
            isBlocked=True,
        )

        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "result": {
                "UF_CRM_1772457154217": 0,
            }
        }
        mock_post.return_value = response

        result = self.client.post(
            reverse("set_is_blocked"),
            {"document_id[2]": "DEAL_12345"},
        )

        client.refresh_from_db()

        self.assertEqual(result.status_code, 200)
        self.assertFalse(client.isBlocked)
