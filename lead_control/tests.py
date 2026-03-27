from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from lead_control.bitrix_api import create_bitrix_task


@override_settings(BITRIX_WEBHOOK_URL="https://example.bitrix24.ru/rest/1/test/")
class LeadControlBitrixAPITests(SimpleTestCase):
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

    @patch("lead_control.bitrix_api._post")
    def test_create_task_does_not_raise_when_binding_not_confirmed(self, post_mock):
        post_mock.side_effect = [
            {"result": 321},
            {"result": {"task": {"id": "321", "ufCrmTask": []}}},
            {"result": True},
            {"result": {"task": {"id": "321", "ufCrmTask": []}}},
            {"result": True},
            {"result": {"task": {"id": "321", "ufCrmTask": []}}},
            {"result": True},
            {"result": {"task": {"id": "321", "ufCrmTask": []}}},
            {"result": True},
            {"result": {"task": {"id": "321", "ufCrmTask": []}}},
            {"result": True},
            {"result": {"task": {"id": "321", "ufCrmTask": []}}},
        ]

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
