import json
import tempfile
from unittest.mock import Mock, patch
from pathlib import Path

from django.test import RequestFactory, TestCase
from django.urls import reverse
from requests import HTTPError

from documents.views import CONTRACT_ACCEPTED_FIELD, _build_contract_token, dogovor


class ContractConfirmationPageTests(TestCase):
    def _response(self, payload):
        response = Mock()
        response.json.return_value = payload
        response.raise_for_status.return_value = None
        return response

    @patch("documents.views.requests.get")
    def test_contract_page_renders_download_link(self, mock_get):
        mock_get.side_effect = [
            self._response(
                {
                    "result": {
                        "TITLE": "Иванов Иван Иванович",
                        "UF_CRM_1745892727271": "42/2026",
                        "UF_CRM_1745892619372": 555,
                        CONTRACT_ACCEPTED_FIELD: 0,
                    }
                }
            ),
            self._response({"result": {"DOWNLOAD_URL": "https://cdn.example.com/dogovor.docx"}}),
        ]

        deal_id = 321
        token = _build_contract_token(str(deal_id))
        response = self.client.get(
            reverse("contract_confirmation_page", args=[deal_id]),
            {"token": token},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Иванов Иван Иванович")
        self.assertContains(response, "https://cdn.example.com/dogovor.docx")

    @patch("documents.views.requests.post")
    @patch("documents.views.requests.get")
    def test_contract_page_post_confirms_deal(self, mock_get, mock_post):
        mock_get.side_effect = [
            self._response(
                {
                    "result": {
                        "TITLE": "Петров Петр Петрович",
                        "UF_CRM_1745892727271": "77/2026",
                        "UF_CRM_1745892619372": 777,
                        CONTRACT_ACCEPTED_FIELD: 0,
                    }
                }
            ),
            self._response({"result": {"DOWNLOAD_URL": "https://cdn.example.com/petrov.docx"}}),
        ]
        mock_post.return_value = self._response({"result": True})

        deal_id = 654
        token = _build_contract_token(str(deal_id))
        response = self.client.post(
            reverse("contract_confirmation_page", args=[deal_id]),
            {"token": token, "agree": "on"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Согласие сохранено")
        mock_post.assert_called_once()
        self.assertEqual(
            mock_post.call_args.kwargs["json"]["fields"][CONTRACT_ACCEPTED_FIELD],
            1,
        )

    def test_contract_page_with_invalid_token_returns_404(self):
        response = self.client.get(
            reverse("contract_confirmation_page", args=[999]),
            {"token": "bad-token"},
        )
        self.assertEqual(response.status_code, 404)

    @patch("documents.views.requests.get")
    def test_contract_page_survives_disk_401(self, mock_get):
        disk_response = Mock()
        disk_response.raise_for_status.side_effect = HTTPError("401 Client Error")

        mock_get.side_effect = [
            self._response(
                {
                    "result": {
                        "TITLE": "Сидоров Сидор Сидорович",
                        "UF_CRM_1745892727271": "88/2026",
                        "UF_CRM_1745892619372": 73840,
                        CONTRACT_ACCEPTED_FIELD: 0,
                    }
                }
            ),
            disk_response,
        ]

        deal_id = 15348
        token = _build_contract_token(str(deal_id))
        response = self.client.get(
            reverse("contract_confirmation_page", args=[deal_id]),
            {"token": token},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Не удалось получить прямую ссылку на файл договора")


class DogovorWebhookTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.documents_dir = Path(self.temp_dir.name)
        (self.documents_dir / "templates_src").mkdir(parents=True, exist_ok=True)
        (self.documents_dir / "generated_docs").mkdir(parents=True, exist_ok=True)
        (self.documents_dir / "templates_src" / "template_2.docx").write_bytes(b"stub")

    def tearDown(self):
        self.temp_dir.cleanup()

    def _response(self, payload):
        response = Mock()
        response.json.return_value = payload
        response.raise_for_status.return_value = None
        return response

    @patch("documents.views.generate_contract")
    @patch("documents.views._get_documents_dir")
    @patch("documents.views._resolve_contract_download_url", return_value="https://cdn.example.com/generated.docx")
    @patch("documents.views._update_contract_link")
    @patch("documents.views.upload_to_bitrix", return_value={"status": "success"})
    @patch("documents.views.get_phone_number", return_value="+79990000000")
    @patch("documents.views._get_deal_data")
    def test_dogovor_saves_confirmation_link_to_bitrix(
        self,
        mock_get_deal_data,
        mock_get_phone_number,
        mock_upload_to_bitrix,
        mock_update_contract_link,
        mock_resolve_contract_download_url,
        mock_get_documents_dir,
        mock_generate_contract,
    ):
        mock_get_documents_dir.return_value = self.documents_dir
        mock_get_deal_data.side_effect = [
            {
                "TITLE": "Иванов Иван Иванович",
                "CONTACT_ID": "11",
                "UF_CRM_1745892727271": "55/2026",
                "UF_CRM_1745888327609": "1990-01-01T00:00:00",
                "UF_CRM_1745889060779": "1234",
                "UF_CRM_1745889067225": "567890",
                "UF_CRM_1745889085935": "ОВД",
                "UF_CRM_1754384630146": "2020-01-01T00:00:00",
                "UF_CRM_1745889094660": "111-222",
                "UF_CRM_1745889105838": "Москва",
                "UF_CRM_1745893079148": "ул. Пушкина",
                "OPPORTUNITY": "100000",
                "UF_CRM_1742457114242": "10000|RUB",
                "UF_CRM_1742468532579": "20000|RUB",
                "UF_CRM_1742480133860": "3",
                "UF_CRM_1742457148727": "5000|RUB",
                "UF_CRM_1742468566169": "2026-04-10T00:00:00",
                "UF_CRM_1745893194511": "15",
                "UF_CRM_1745892619372": 999,
            },
            {
                "UF_CRM_1745892619372": 999,
            },
        ]
        mock_generate_contract.side_effect = lambda *args, **kwargs: (
            self.documents_dir / "generated_docs" / "dogovor_123.docx"
        ).write_bytes(b"generated")

        request = self.factory.post(
            reverse("dogovor"),
            {"document_id[2]": "DEAL_123"},
        )
        response = dogovor(request)

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)
        self.assertIn("confirmation_url", payload)
        mock_update_contract_link.assert_called_once_with("123", payload["confirmation_url"])
        self.assertEqual(payload["contract_download_url"], "https://cdn.example.com/generated.docx")
