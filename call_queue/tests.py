from unittest.mock import Mock, patch
from pathlib import Path
import tempfile

import requests
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from call_queue.models import (
    BitrixSyncLog,
    CallAttempt,
    CallEntityType,
    CallQueueItem,
    CallQueueItemStatus,
    CallResult,
    CallSession,
    CallSessionStatus,
)
from call_queue.services.bitrix.deal_service import BitrixDealService
from call_queue.services.queue_service import QueueService
from call_queue.services.telephony.megafon import MegafonAPIError, MegafonTelephonyService
from leadreport.models import SalesManager

User = get_user_model()


class QueueServiceTests(TestCase):
    def setUp(self):
        self.user_1 = User.objects.create_user(username="manager_1", password="pass")
        self.user_2 = User.objects.create_user(username="manager_2", password="pass")
        self.deal_service = Mock()
        self.timeline_service = Mock()
        self.service = QueueService(
            deal_service=self.deal_service,
            timeline_service=self.timeline_service,
        )

    def test_create_session_with_queue_populates_items(self):
        self.deal_service.fetch_deals.return_value = [
            {
                "bitrix_deal_id": 101,
                "entity_type": CallEntityType.DEAL,
                "bitrix_entity_id": 101,
                "client_name": "Иван",
                "phone": "+79990001122",
                "bitrix_url": "https://example.bitrix24.ru/crm/deal/details/101/",
            },
            {
                "bitrix_deal_id": 102,
                "entity_type": CallEntityType.DEAL,
                "bitrix_entity_id": 102,
                "client_name": "Петр",
                "phone": "+79990001123",
                "bitrix_url": "https://example.bitrix24.ru/crm/deal/details/102/",
            },
        ]

        session = self.service.create_session_with_queue(
            manager=self.user_1,
            filters={
                "date_from": timezone.localdate(),
                "date_to": timezone.localdate(),
                "entity_type": CallEntityType.DEAL,
                "stage_id": "",
                "source_id": "",
                "responsible_id": "",
                "only_unanswered": False,
                "only_without_repeat": False,
            },
        )

        self.assertEqual(session.total_items, 2)
        self.assertEqual(CallQueueItem.objects.filter(session=session).count(), 2)

    def test_get_next_item_does_not_double_assign_same_lead(self):
        session = CallSession.objects.create(
            created_by=self.user_1,
            entity_type=CallEntityType.DEAL,
            date_from=timezone.localdate(),
            date_to=timezone.localdate(),
            status=CallSessionStatus.ACTIVE,
        )
        item = CallQueueItem.objects.create(
            session=session,
            entity_type=CallEntityType.DEAL,
            bitrix_entity_id=101,
            client_name="Лид",
        )

        first = self.service.get_next_item_for_manager(session, self.user_1)
        second = self.service.get_next_item_for_manager(session, self.user_2)

        self.assertEqual(first.pk, item.pk)
        self.assertIsNone(second)
        item.refresh_from_db()
        self.assertEqual(item.assigned_to, self.user_1)
        self.assertEqual(item.status, CallQueueItemStatus.IN_PROGRESS)

    def test_process_call_result_creates_attempt_and_updates_item(self):
        session = CallSession.objects.create(
            created_by=self.user_1,
            entity_type=CallEntityType.DEAL,
            date_from=timezone.localdate(),
            date_to=timezone.localdate(),
            status=CallSessionStatus.ACTIVE,
        )
        item = CallQueueItem.objects.create(
            session=session,
            entity_type=CallEntityType.DEAL,
            bitrix_entity_id=101,
            client_name="Лид",
            assigned_to=self.user_1,
            locked_at=timezone.now(),
            status=CallQueueItemStatus.IN_PROGRESS,
        )
        self.deal_service.update_entity_after_call.return_value = {"result": True}
        self.timeline_service.add_comment.return_value = {"result": 1}

        result = self.service.process_call_result(
            queue_item=item,
            manager=self.user_1,
            result=CallResult.SUCCESS,
            comment="Договорились",
        )

        item.refresh_from_db()
        self.assertEqual(CallAttempt.objects.filter(queue_item=item).count(), 1)
        self.assertEqual(item.status, CallQueueItemStatus.DONE)
        self.assertTrue(item.needs_manual_processing)
        self.assertEqual(item.last_call_result, CallResult.SUCCESS)
        self.assertEqual(result["sync_error"], "")

    def test_failed_result_marks_repeat_unanswered_on_second_attempt(self):
        session = CallSession.objects.create(
            created_by=self.user_1,
            entity_type=CallEntityType.DEAL,
            date_from=timezone.localdate(),
            date_to=timezone.localdate(),
            status=CallSessionStatus.ACTIVE,
        )
        item = CallQueueItem.objects.create(
            session=session,
            entity_type=CallEntityType.DEAL,
            bitrix_entity_id=101,
            client_name="Лид",
            assigned_to=self.user_1,
            locked_at=timezone.now(),
            status=CallQueueItemStatus.IN_PROGRESS,
            attempts_count=1,
        )
        self.deal_service.update_entity_after_call.return_value = {"result": True}
        self.timeline_service.add_comment.return_value = {"result": 1}

        self.service.process_call_result(
            queue_item=item,
            manager=self.user_1,
            result=CallResult.NO_ANSWER,
        )

        item.refresh_from_db()
        self.assertEqual(item.status, CallQueueItemStatus.FAILED)
        self.assertTrue(item.repeat_unanswered)

    def test_get_next_item_returns_next_requeueable_lead(self):
        session = CallSession.objects.create(
            created_by=self.user_1,
            entity_type=CallEntityType.DEAL,
            date_from=timezone.localdate(),
            date_to=timezone.localdate(),
            status=CallSessionStatus.ACTIVE,
        )
        CallQueueItem.objects.create(
            session=session,
            entity_type=CallEntityType.DEAL,
            bitrix_entity_id=101,
            client_name="Отложен",
            status=CallQueueItemStatus.POSTPONED,
        )
        fresh_item = CallQueueItem.objects.create(
            session=session,
            entity_type=CallEntityType.DEAL,
            bitrix_entity_id=102,
            client_name="Новый",
            status=CallQueueItemStatus.NEW,
        )

        next_item = self.service.get_next_item_for_manager(session, self.user_1)
        self.assertEqual(next_item.pk, fresh_item.pk)

    def test_bitrix_sync_error_is_logged_without_breaking_flow(self):
        session = CallSession.objects.create(
            created_by=self.user_1,
            entity_type=CallEntityType.DEAL,
            date_from=timezone.localdate(),
            date_to=timezone.localdate(),
            status=CallSessionStatus.ACTIVE,
        )
        item = CallQueueItem.objects.create(
            session=session,
            entity_type=CallEntityType.DEAL,
            bitrix_entity_id=101,
            client_name="Лид",
            assigned_to=self.user_1,
            locked_at=timezone.now(),
            status=CallQueueItemStatus.IN_PROGRESS,
        )
        self.deal_service.update_entity_after_call.side_effect = RuntimeError("Bitrix down")

        result = self.service.process_call_result(
            queue_item=item,
            manager=self.user_1,
            result=CallResult.POSTPONED,
        )

        item.refresh_from_db()
        self.assertEqual(item.status, CallQueueItemStatus.POSTPONED)
        self.assertEqual(BitrixSyncLog.objects.filter(success=False).count(), 1)
        self.assertIn("Bitrix down", result["sync_error"])


class CallQueueAccessTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="plain_user", password="pass")
        self.manager_user = User.objects.create_user(username="sales_user", password="pass")
        self.sales_manager = SalesManager.objects.create(
            user=self.manager_user,
            bitrix_user_id=777,
            name="Менеджер продаж",
            is_active=True,
            megafon_user="manager-login",
            megafon_clid="79990000000",
        )

    @patch("call_queue.services.bitrix.deal_service.BitrixDealService.get_stage_choices", return_value=[])
    @patch("call_queue.services.bitrix.deal_service.BitrixDealService.get_source_choices", return_value=[])
    @patch("call_queue.services.bitrix.deal_service.BitrixDealService.get_responsible_choices", return_value=[])
    def test_dashboard_denies_access_without_sales_manager_profile(self, *_mocks):
        self.client.force_login(self.user)

        response = self.client.get(reverse("call_queue:dashboard"))

        self.assertEqual(response.status_code, 403)

    @patch("call_queue.services.bitrix.deal_service.BitrixDealService.get_stage_choices", return_value=[])
    @patch("call_queue.services.bitrix.deal_service.BitrixDealService.get_source_choices", return_value=[])
    @patch("call_queue.services.bitrix.deal_service.BitrixDealService.get_responsible_choices", return_value=[])
    def test_dashboard_allows_active_sales_manager(self, *_mocks):
        self.client.force_login(self.manager_user)

        response = self.client.get(reverse("call_queue:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["sales_manager_profile"], self.sales_manager)


@override_settings(MEGAFON_VATS_CRM_AUTH_KEY="test_megafon_secret")
class MegafonWebhookTests(TestCase):
    def test_webhook_rejects_invalid_key(self):
        response = self.client.post(
            reverse("call_queue:megafon_webhook"),
            data='{"call_id":"123"}',
            content_type="application/json",
            HTTP_X_CRM_AUTH="wrong",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(BitrixSyncLog.objects.filter(entity_type="megafon_webhook", success=False).count(), 1)

    def test_webhook_accepts_valid_key(self):
        response = self.client.post(
            reverse("call_queue:megafon_webhook"),
            data='{"call_id":"123","status":"completed"}',
            content_type="application/json",
            HTTP_X_CRM_AUTH="test_megafon_secret",
        )

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content.decode("utf-8"), {"ok": True})
        self.assertEqual(BitrixSyncLog.objects.filter(entity_type="megafon_webhook", success=True).count(), 1)

    def test_webhook_accepts_valid_crm_token(self):
        response = self.client.post(
            reverse("call_queue:megafon_webhook"),
            data={
                "crm_token": "test_megafon_secret",
                "callid": "ABC123",
                "cmd": "history",
                "status": "Success",
            },
        )

        self.assertEqual(response.status_code, 200)
        log = BitrixSyncLog.objects.get(entity_type="megafon_webhook", entity_id="ABC123", success=True)
        self.assertEqual(log.action, "history:Success")

    @override_settings(MEGAFON_VATS_CRM_AUTH_KEY="test_megafon_secret")
    def test_webhook_writes_to_log_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "megafon.log"
            with self.settings(MEGAFON_WEBHOOK_LOG_FILE=str(log_file)):
                response = self.client.post(
                    reverse("call_queue:megafon_webhook"),
                    data='{"callid":"123","status":"completed"}',
                    content_type="application/json",
                    HTTP_X_CRM_AUTH="test_megafon_secret",
                )

            self.assertEqual(response.status_code, 200)
            self.assertTrue(log_file.exists())
            content = log_file.read_text(encoding="utf-8")
            self.assertIn("incoming_callback_raw", content)
            self.assertIn('"callid": "123"', content)


class BitrixDealServiceFilterTests(TestCase):
    def test_only_unanswered_uses_deal_preparation_stage(self):
        client = Mock()
        client.paginated_call.return_value = []
        service = BitrixDealService(client=client)

        service.fetch_deals(
            {
                "entity_type": CallEntityType.DEAL,
                "date_from": timezone.localdate().isoformat(),
                "date_to": timezone.localdate().isoformat(),
                "stage_id": "",
                "source_id": "",
                "responsible_id": "",
                "only_unanswered": True,
                "only_without_repeat": False,
            }
        )

        params = client.paginated_call.call_args.args[1]
        self.assertEqual(params["filter"]["STAGE_ID"], "PREPARATION")

    def test_only_unanswered_uses_lead_in_process_status(self):
        client = Mock()
        client.paginated_call.return_value = []
        service = BitrixDealService(client=client)

        service.fetch_deals(
            {
                "entity_type": CallEntityType.LEAD,
                "date_from": timezone.localdate().isoformat(),
                "date_to": timezone.localdate().isoformat(),
                "stage_id": "",
                "source_id": "",
                "responsible_id": "",
                "only_unanswered": True,
                "only_without_repeat": False,
            }
        )

        params = client.paginated_call.call_args.args[1]
        self.assertEqual(params["filter"]["STATUS_ID"], "IN_PROCESS")


class MegafonTelephonyTests(TestCase):
    @override_settings(
        MEGAFON_VATS_API_URL="https://example.megafon.ru/crmapi/v1",
        MEGAFON_VATS_API_KEY="secret",
        MEGAFON_VATS_AUTH_MODE="header",
        MEGAFON_VATS_AUTH_HEADER="X-API-KEY",
    )
    @patch("call_queue.services.telephony.megafon.requests.post")
    def test_make_call_sends_expected_payload(self, post_mock):
        response = Mock()
        response.json.return_value = {"callid": "12345", "clid": "79990000000"}
        response.raise_for_status.return_value = None
        post_mock.return_value = response

        service = MegafonTelephonyService()
        data = service.make_call(
            phone="74952005060",
            user="manager-login",
            clid="79990000000",
            show_phone=True,
        )

        self.assertEqual(data["callid"], "12345")
        post_mock.assert_called_once()
        _, kwargs = post_mock.call_args
        self.assertEqual(kwargs["json"]["phone"], "74952005060")
        self.assertEqual(kwargs["json"]["user"], "manager-login")
        self.assertEqual(kwargs["json"]["clid"], "79990000000")
        self.assertEqual(kwargs["headers"]["X-API-KEY"], "secret")

    def test_make_call_requires_user_or_group(self):
        service = MegafonTelephonyService(
            base_url="https://example.megafon.ru/crmapi/v1",
            api_key="secret",
        )

        with self.assertRaises(MegafonAPIError):
            service.make_call(phone="74952005060")

    @override_settings(
        MEGAFON_VATS_API_URL="https://configured.megafon.ru/crmapi/v1",
        MEGAFON_VATS_API_KEY="configured-secret",
        MEGAFON_VATS_AUTH_MODE="header",
        MEGAFON_VATS_AUTH_HEADER="X-API-KEY",
    )
    @patch("call_queue.services.telephony.megafon.requests.post")
    def test_make_call_uses_settings_when_constructor_args_omitted(self, post_mock):
        response = Mock()
        response.json.return_value = {"callid": "12345"}
        response.raise_for_status.return_value = None
        post_mock.return_value = response

        service = MegafonTelephonyService()
        service.make_call(phone="74952005060", user="manager-login")

        _, kwargs = post_mock.call_args
        self.assertEqual(kwargs["headers"]["X-API-KEY"], "configured-secret")
        self.assertEqual(post_mock.call_args.args[0], "https://configured.megafon.ru/crmapi/v1/makecall")

    @patch("call_queue.services.telephony.megafon.requests.post")
    def test_make_call_prefers_user_over_group(self, post_mock):
        response = Mock()
        response.json.return_value = {"callid": "12345"}
        response.raise_for_status.return_value = None
        post_mock.return_value = response

        service = MegafonTelephonyService(
            base_url="https://example.megafon.ru/crmapi/v1",
            api_key="secret",
        )
        service.make_call(phone="74952005060", user="manager-login", group="sales-group")

        _, kwargs = post_mock.call_args
        self.assertEqual(kwargs["json"]["user"], "manager-login")
        self.assertNotIn("group", kwargs["json"])

    @patch("call_queue.services.telephony.megafon.requests.post")
    def test_make_call_raises_api_error_with_response_details(self, post_mock):
        response = Mock()
        response.status_code = 400
        response.json.return_value = {"error": "invalid user"}
        response.text = '{"error":"invalid user"}'
        response.raise_for_status.side_effect = requests.HTTPError("400 Client Error", response=response)
        post_mock.return_value = response

        service = MegafonTelephonyService(
            base_url="https://example.megafon.ru/crmapi/v1",
            api_key="secret",
        )

        with self.assertRaises(MegafonAPIError) as exc:
            service.make_call(phone="74952005060", user="manager-login")

        self.assertIn("HTTP 400", str(exc.exception))
        self.assertIn("invalid user", str(exc.exception))


class CallQueueMegafonViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="sales_call_user", password="pass")
        self.sales_manager = SalesManager.objects.create(
            user=self.user,
            bitrix_user_id=888,
            name="Менеджер обзвона",
            is_active=True,
            megafon_user="manager-login",
            megafon_clid="79990000000",
        )
        self.session = CallSession.objects.create(
            created_by=self.user,
            entity_type=CallEntityType.DEAL,
            date_from=timezone.localdate(),
            date_to=timezone.localdate(),
            status=CallSessionStatus.ACTIVE,
        )
        self.item = CallQueueItem.objects.create(
            session=self.session,
            entity_type=CallEntityType.DEAL,
            bitrix_entity_id=555,
            client_name="Клиент",
            phone="74952005060",
            assigned_to=self.user,
            locked_at=timezone.now(),
            status=CallQueueItemStatus.IN_PROGRESS,
        )

    @patch("call_queue.views.MegafonTelephonyService.make_call")
    def test_start_call_saves_provider_call_id(self, make_call_mock):
        make_call_mock.return_value = {"callid": "2015948553", "clid": "79990000000"}
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("call_queue:session_detail", kwargs={"session_id": self.session.pk}),
            {"action": "start_call"},
        )

        self.assertEqual(response.status_code, 302)
        self.item.refresh_from_db()
        self.assertEqual(self.item.last_provider_call_id, "2015948553")
        self.assertEqual(BitrixSyncLog.objects.filter(entity_type="megafon_call", success=True).count(), 1)

    def test_call_status_endpoint_returns_success_marker(self):
        BitrixSyncLog.objects.create(
            entity_type="megafon_webhook",
            entity_id="CALL42",
            action="event:ACCEPTED",
            request_payload={"payload": {"cmd": "event", "type": "ACCEPTED", "direction": "out", "callid": "CALL42"}},
            response_payload={"accepted": True},
            success=True,
        )
        BitrixSyncLog.objects.create(
            entity_type="megafon_webhook",
            entity_id="CALL42",
            action="history:Success",
            request_payload={"payload": {"cmd": "history", "status": "Success", "callid": "CALL42"}},
            response_payload={"accepted": True},
            success=True,
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("call_queue:megafon_call_status"), {"callid": "CALL42"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["snapshot"]["marker"]["state"], "success")

    def test_call_status_endpoint_returns_unreachable_marker(self):
        BitrixSyncLog.objects.create(
            entity_type="megafon_webhook",
            entity_id="CALL99",
            action="history:missed",
            request_payload={"payload": {"cmd": "history", "status": "missed", "callid": "CALL99"}},
            response_payload={"accepted": True},
            success=True,
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("call_queue:megafon_call_status"), {"callid": "CALL99"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["snapshot"]["marker"]["state"], "unreachable")

    @patch("call_queue.views.MegafonTelephonyService.make_call")
    def test_manual_test_call_page_starts_call(self, make_call_mock):
        make_call_mock.return_value = {"callid": "9001", "clid": "79990000000"}
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("call_queue:megafon_test_call"),
            {
                "phone": "74952005060",
                "sales_manager": self.sales_manager.pk,
                "clid": "",
                "show_phone": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        make_call_mock.assert_called_once()
