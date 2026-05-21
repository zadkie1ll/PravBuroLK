import json
from unittest.mock import Mock, patch
from datetime import datetime
from types import SimpleNamespace

from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone

from payments.views import BitrixCreateClientFromDealView, payment_callback

class PaymentCallbackTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @override_settings(BITRIX_WEBHOOK_URL="https://example.bitrix24.ru/rest/1/test/")
    @patch("payments.views.requests.get")
    @patch("payments.views.requests.post")
    def test_contract_payment_callback_adds_bitrix_timeline_comment_and_task(self, post_mock, get_mock):
        response_mock = Mock()
        response_mock.raise_for_status.return_value = None
        comment_response = Mock()
        comment_response.raise_for_status.return_value = None
        comment_response.json.return_value = {"result": 1}
        task_response = Mock()
        task_response.raise_for_status.return_value = None
        task_response.json.return_value = {"result": {"task": {"id": "987"}}}
        post_mock.side_effect = [comment_response, task_response]
        get_response = Mock()
        get_response.raise_for_status.return_value = None
        get_response.json.return_value = {"result": {"ID": "321", "ASSIGNED_BY_ID": "555"}}
        get_mock.return_value = get_response

        request = self.factory.get(
            "/callback/",
            {
                "orderNumber": "contract-321-1715000000",
                "status": "1",
                "operation": "deposited",
                "amount": "2000000",
            },
        )
        response = payment_callback(request)

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)
        self.assertEqual(payload["deal_id"], 321)
        self.assertTrue(payload["comment_added"])
        self.assertTrue(payload["task_created"])
        self.assertEqual(payload["task_id"], 987)
        self.assertEqual(post_mock.call_count, 2)
        self.assertEqual(get_mock.call_args.args[0], "https://example.bitrix24.ru/rest/1/test/crm.deal.get")
        self.assertEqual(get_mock.call_args.kwargs["params"]["ID"], "321")

        comment_call = post_mock.call_args_list[0]
        self.assertEqual(comment_call.args[0], "https://example.bitrix24.ru/rest/1/test/crm.timeline.comment.add")
        self.assertEqual(comment_call.kwargs["data"]["fields[ENTITY_ID]"], "321")
        self.assertEqual(comment_call.kwargs["data"]["fields[ENTITY_TYPE]"], "deal")
        self.assertIn("Поступила успешная оплата по договору", comment_call.kwargs["data"]["fields[COMMENT]"])
        self.assertIn("20000", comment_call.kwargs["data"]["fields[COMMENT]"])

        task_call = post_mock.call_args_list[1]
        task_data = task_call.kwargs["data"]
        self.assertEqual(task_call.args[0], "https://example.bitrix24.ru/rest/1/test/tasks.task.add")
        self.assertEqual(task_data["fields[TITLE]"], "Клиент внес оплату")
        self.assertEqual(
            task_data["fields[DESCRIPTION]"],
            "Клиент внес оплату, необходимо перевести его в отдел сопровождения",
        )
        self.assertEqual(task_data["fields[RESPONSIBLE_ID]"], "555")
        deadline = datetime.fromisoformat(task_data["fields[DEADLINE]"])
        delta = deadline - timezone.now()
        self.assertGreater(delta.total_seconds(), 23 * 60 * 60)
        self.assertLess(delta.total_seconds(), 25 * 60 * 60)

    def test_payment_callback_ignores_non_successful_event(self):
        request = self.factory.get(
            "/callback/",
            {
                "orderNumber": "contract-321-1715000000",
                "status": "0",
                "operation": "created",
                "amount": "2000000",
            },
        )
        response = payment_callback(request)

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)
        self.assertEqual(payload["status"], "ignored")


class BitrixCreateClientFromDealViewTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @override_settings(BITRIX_WEBHOOK_URL="https://example.bitrix24.ru/rest/1/test/")
    @patch("payments.views.build_withdrawals_bitrix_fields", return_value={})
    @patch("clients.services.ClientService.create_client_with_contract")
    @patch("payments.views.requests.post")
    @patch("payments.views.requests.get")
    @patch("payments.views.get_deal_data_from_bitrix")
    def test_falls_back_to_deal_title_when_custom_name_fields_are_empty(
        self,
        get_deal_mock,
        requests_get_mock,
        requests_post_mock,
        create_client_mock,
        build_withdrawals_mock,
    ):
        get_deal_mock.return_value = (
            {
                "ID": "123",
                "TITLE": "Иванов Иван Иванович",
                "CONTACT_ID": "456",
                "UF_CRM_1754380684375": "",
                "UF_CRM_1754380678904": "",
                "UF_CRM_1754380692399": "",
                "OPPORTUNITY": "100000|RUB",
            },
            None,
        )
        contact_response = Mock()
        contact_response.status_code = 200
        contact_response.json.return_value = {
            "result": {
                "PHONE": [{"VALUE": "+79990000000"}],
                "NAME": "",
                "LAST_NAME": "",
                "SECOND_NAME": "",
            }
        }
        requests_get_mock.return_value = contact_response

        bitrix_update_response = Mock()
        bitrix_update_response.json.return_value = {"result": True}
        requests_post_mock.return_value = bitrix_update_response

        client = SimpleNamespace(
            id=10,
            user=SimpleNamespace(username="+79990000000"),
        )
        contract = SimpleNamespace(id=20)
        plan = SimpleNamespace(id=30)
        create_client_mock.return_value = (client, contract, plan)

        request = self.factory.post(
            "/bitrix/webhook/create-client-from-deal/",
            {"document_id[2]": "DEAL_123"},
        )
        response = BitrixCreateClientFromDealView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        create_kwargs = create_client_mock.call_args.kwargs
        self.assertEqual(create_kwargs["name"], "Иван")
        self.assertEqual(create_kwargs["surname"], "Иванов")
        self.assertEqual(create_kwargs["middlename"], "Иванович")
        self.assertEqual(json.loads(response.content)["message"], "Клиент успешно создан и данные отправлены в Битрикс")
