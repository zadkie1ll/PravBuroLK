from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from clients.models import Client

from .models import ClientWithdrawalRecord
from .services import build_withdrawals_summary


class ClientWithdrawalRecordTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(username="tester", password="secret")
        self.client_obj = Client.objects.create(
            user=user,
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

