from unittest.mock import Mock, patch

from django.test import TestCase, override_settings
from django.urls import reverse


class PaymentCallbackTests(TestCase):
    @override_settings(BITRIX_WEBHOOK_URL="https://example.bitrix24.ru/rest/1/test/")
    @patch("payments.views.requests.post")
    def test_contract_payment_callback_adds_bitrix_timeline_comment(self, post_mock):
        response_mock = Mock()
        response_mock.raise_for_status.return_value = None
        response_mock.json.return_value = {"result": 1}
        post_mock.return_value = response_mock

        response = self.client.get(
            reverse("payment_callback"),
            {
                "orderNumber": "contract-321-1715000000",
                "status": "1",
                "operation": "deposited",
                "amount": "2000000",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["deal_id"], 321)
        self.assertTrue(response.json()["comment_added"])
        self.assertEqual(
            post_mock.call_args.args[0],
            "https://example.bitrix24.ru/rest/1/test/crm.timeline.comment.add",
        )
        self.assertEqual(post_mock.call_args.kwargs["data"]["fields[ENTITY_ID]"], "321")
        self.assertEqual(post_mock.call_args.kwargs["data"]["fields[ENTITY_TYPE]"], "deal")
        self.assertIn("Поступила успешная оплата по договору", post_mock.call_args.kwargs["data"]["fields[COMMENT]"])
        self.assertIn("20000", post_mock.call_args.kwargs["data"]["fields[COMMENT]"])

    def test_payment_callback_ignores_non_successful_event(self):
        response = self.client.get(
            reverse("payment_callback"),
            {
                "orderNumber": "contract-321-1715000000",
                "status": "0",
                "operation": "created",
                "amount": "2000000",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ignored")
