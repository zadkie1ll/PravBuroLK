from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client as DjangoClient
from django.test import TestCase
from django.urls import reverse

from clients.models import Client

from .models import ClientWithdrawalRecord
from .services import build_withdrawals_summary, get_total_tail_amount


class ClientWithdrawalRecordTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tester", password="secret")
        self.client_obj = Client.objects.create(
            user=self.user,
            name="Иван",
            surname="Иванов",
            middlename="Иванович",
            bitrix_id="123",
        )

    def test_tail_amount_is_calculated_automatically(self):
        record = ClientWithdrawalRecord.objects.create(
            client=self.client_obj,
            withdrawal_date="2026-03-20",
            transfer_date="2026-03-21",
            withdrawal_amount=Decimal("11000.00"),
            transferred_amount=Decimal("10000.00"),
        )

        self.assertEqual(record.tail_amount, Decimal("1000.00"))

    def test_summary_contains_record_values(self):
        ClientWithdrawalRecord.objects.create(
            client=self.client_obj,
            withdrawal_date="2026-03-20",
            transfer_date="2026-03-21",
            withdrawal_amount=Decimal("11000.00"),
            transferred_amount=Decimal("10000.00"),
        )

        summary = build_withdrawals_summary(self.client_obj)

        self.assertIn("20.03.2026", summary)
        self.assertIn("21.03.2026", summary)
        self.assertIn("1000.00", summary)

    def test_total_tail_amount_sums_all_client_withdrawals(self):
        ClientWithdrawalRecord.objects.create(
            client=self.client_obj,
            withdrawal_amount=Decimal("11000.00"),
            transferred_amount=Decimal("10000.00"),
        )
        ClientWithdrawalRecord.objects.create(
            client=self.client_obj,
            withdrawal_amount=Decimal("5000.00"),
            transferred_amount=Decimal("1250.00"),
        )

        self.assertEqual(get_total_tail_amount(self.client_obj), Decimal("4750.00"))

    def test_record_can_be_created_without_withdrawal_fields(self):
        record = ClientWithdrawalRecord.objects.create(client=self.client_obj)

        summary = build_withdrawals_summary(self.client_obj)

        self.assertIsNone(record.withdrawal_date)
        self.assertIsNone(record.transfer_date)
        self.assertIsNone(record.withdrawal_amount)
        self.assertIsNone(record.transferred_amount)
        self.assertEqual(record.tail_amount, Decimal("0.00"))
        self.assertIn("- | - | - | - | 0.00", summary)

    def test_page_contains_edit_form_for_existing_records(self):
        record = ClientWithdrawalRecord.objects.create(
            client=self.client_obj,
            withdrawal_date="2026-03-20",
            transfer_date="2026-03-21",
            withdrawal_amount=Decimal("11000.00"),
            transferred_amount=Decimal("10000.00"),
            comment="Старый комментарий",
        )
        django_client = DjangoClient()
        django_client.force_login(self.user)

        response = django_client.get(reverse("client_withdrawals_page", args=[self.client_obj.id]))

        self.assertContains(response, reverse("update_withdrawal_record", args=[record.id]))
        self.assertContains(response, 'data-edit-toggle="')
        self.assertContains(response, "Старый комментарий")

    @patch("client_withdrawals.views.sync_withdrawals_to_bitrix", return_value=True)
    def test_create_withdrawal_record_accepts_empty_withdrawal_fields(self, sync_mock):
        django_client = DjangoClient()
        django_client.force_login(self.user)

        response = django_client.post(
            reverse("create_withdrawal_record", args=[self.client_obj.id]),
            {
                "withdrawal_date": "",
                "transfer_date": "",
                "withdrawal_amount": "",
                "transferred_amount": "",
                "comment": "Заполнить позже",
            },
        )

        record = ClientWithdrawalRecord.objects.get(client=self.client_obj)
        self.assertRedirects(response, reverse("client_withdrawals_page", args=[self.client_obj.id]))
        self.assertIsNone(record.withdrawal_date)
        self.assertIsNone(record.transfer_date)
        self.assertIsNone(record.withdrawal_amount)
        self.assertIsNone(record.transferred_amount)
        self.assertEqual(record.tail_amount, Decimal("0.00"))
        sync_mock.assert_called_once_with(self.client_obj)

    @patch("client_withdrawals.views.sync_withdrawals_to_bitrix", return_value=True)
    def test_update_withdrawal_record_changes_saved_values(self, sync_mock):
        record = ClientWithdrawalRecord.objects.create(
            client=self.client_obj,
            withdrawal_date="2026-03-20",
            transfer_date="2026-03-21",
            withdrawal_amount=Decimal("11000.00"),
            transferred_amount=Decimal("10000.00"),
            comment="Старый комментарий",
        )
        django_client = DjangoClient()
        django_client.force_login(self.user)

        response = django_client.post(
            reverse("update_withdrawal_record", args=[record.id]),
            {
                "withdrawal_date": "2026-04-01",
                "transfer_date": "",
                "withdrawal_amount": "12000.50",
                "transferred_amount": "2000.25",
                "comment": "Новый комментарий",
            },
        )

        record.refresh_from_db()
        self.assertRedirects(response, reverse("client_withdrawals_page", args=[self.client_obj.id]))
        self.assertEqual(record.withdrawal_amount, Decimal("12000.50"))
        self.assertEqual(record.transferred_amount, Decimal("2000.25"))
        self.assertEqual(record.tail_amount, Decimal("10000.25"))
        self.assertEqual(record.comment, "Новый комментарий")
        sync_mock.assert_called_once_with(self.client_obj)
