from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, override_settings

from lead_control.bitrix_api import create_bitrix_task
from lead_control.models import LeadMonitor
from lead_control.services import resolve_moderator_task_deal_id


@override_settings(BITRIX_WEBHOOK_URL="https://example.bitrix24.ru/rest/1/test/")
class LeadControlBitrixAPITests(SimpleTestCase):
    @patch("lead_control.bitrix_api._post")
    def test_create_task_sets_deadline(self, post_mock):
        post_mock.return_value = {"result": 321}

        deadline = "2026-08-27T15:30:00+03:00"
        task_id = create_bitrix_task(
            title="Test task",
            description="Description",
            responsible_id=10,
            deadline=deadline,
        )

        self.assertEqual(task_id, 321)
        self.assertEqual(
            post_mock.call_args.args[1]["fields"]["DEADLINE"],
            deadline,
        )

    @patch("lead_control.bitrix_api._post")
    def test_create_task_keeps_existing_deal_binding(self, post_mock):
        post_mock.side_effect = [
            {"result": 321},
            {"result": {"task": {"id": "321", "ufCrmTask": ["CRM_DEAL_555"]}}},
        ]

        task_id = create_bitrix_task(
            title="Test task",
            description="Description",
            responsible_id=10,
            deal_id=555,
        )

        self.assertEqual(task_id, 321)
        self.assertEqual(post_mock.call_count, 2)
        self.assertEqual(post_mock.call_args_list[0].args[0], "tasks.task.add")
        self.assertEqual(
            post_mock.call_args_list[0].args[1]["fields"]["UF_CRM_TASK"],
            ["CRM_DEAL_555", "D_555"],
        )
        self.assertEqual(
            post_mock.call_args_list[0].args[1]["fields"]["UF_CRM_TASK_DEAL"],
            ["555"],
        )
        self.assertEqual(post_mock.call_args_list[1].args[0], "tasks.task.get")

    @patch("lead_control.bitrix_api._post")
    def test_create_task_updates_when_binding_missing_after_create(self, post_mock):
        post_mock.side_effect = [
            {"result": 321},
            {"result": {"task": {"id": "321", "ufCrmTask": []}}},
            {"result": True},
            {"result": {"task": {"id": "321", "ufCrmTask": ["CRM_DEAL_555"]}}},
        ]

        task_id = create_bitrix_task(
            title="Test task",
            description="Description",
            responsible_id=10,
            deal_id=555,
        )

        self.assertEqual(task_id, 321)
        self.assertEqual(post_mock.call_args_list[2].args[0], "tasks.task.update")
        self.assertEqual(
            post_mock.call_args_list[2].args[1],
            {"taskId": 321, "fields": {"UF_CRM_TASK": ["CRM_DEAL_555", "D_555"]}},
        )

    @patch("lead_control.bitrix_api._post_form")
    @patch("lead_control.bitrix_api._post")
    def test_create_task_does_not_raise_when_binding_not_confirmed(self, post_mock, post_form_mock):
        def post_side_effect(method_name, payload):
            if method_name == "tasks.task.add":
                return {"result": 321}
            if method_name == "tasks.task.get":
                return {"result": {"task": {"id": "321", "ufCrmTask": []}}}
            if method_name == "tasks.task.update":
                return {"result": True}
            raise AssertionError(f"Unexpected method: {method_name}")

        post_mock.side_effect = post_side_effect
        post_form_mock.return_value = {"result": True}

        task_id = create_bitrix_task(
            title="Test task",
            description="Description",
            responsible_id=10,
            deal_id=555,
        )

        self.assertEqual(task_id, 321)

    @patch("lead_control.bitrix_api._post")
    def test_create_task_accepts_legacy_deal_binding(self, post_mock):
        post_mock.side_effect = [
            {"result": 321},
            {"result": {"task": {"id": "321", "ufCrmTask": ["D_555"]}}},
        ]

        task_id = create_bitrix_task(
            title="Test task",
            description="Description",
            responsible_id=10,
            deal_id=555,
        )

        self.assertEqual(task_id, 321)
        self.assertEqual(post_mock.call_count, 2)


@override_settings(LEAD_CONTROL_SALES_DEAL_CATEGORY_ID=2)
class LeadControlServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.monitor = LeadMonitor.objects.create(
            bitrix_deal_id=555,
            moderator_bitrix_user_id=777,
            responsible_bitrix_user_id=888,
        )

    @patch("lead_control.services.find_deals_by_contact_and_category")
    def test_resolve_moderator_task_deal_id_prefers_sales_deal(self, find_deals_mock):
        find_deals_mock.return_value = [{"ID": "7777"}]

        resolved_deal_id = resolve_moderator_task_deal_id(
            self.monitor,
            {"CONTACT_ID": "123"},
        )

        self.assertEqual(resolved_deal_id, 7777)
        find_deals_mock.assert_called_once_with(123, 2, exclude_deal_id=555)

    @patch("lead_control.services.find_deals_by_contact_and_category")
    def test_resolve_moderator_task_deal_id_falls_back_to_monitor_deal(self, find_deals_mock):
        find_deals_mock.return_value = []

        resolved_deal_id = resolve_moderator_task_deal_id(
            self.monitor,
            {"CONTACT_ID": "123"},
        )

        self.assertEqual(resolved_deal_id, 555)
