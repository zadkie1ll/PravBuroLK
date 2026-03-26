from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse


class BuildConsultationTests(TestCase):
    @patch("bitrix.views.upload_to_bitrix")
    @patch("bitrix.views.generate_pdf")
    @patch("bitrix.views.calculate_km")
    @patch("bitrix.views.PmRate.get_for_region_on")
    @patch("bitrix.views.BitrixClient.get_user_with_photo")
    @patch("bitrix.views.get_deal_data_from_bitrix")
    def test_build_consultation_returns_pdf(
        self,
        mock_get_deal_data,
        mock_get_user_with_photo,
        mock_get_pm_rate,
        mock_calculate_km,
        mock_generate_pdf,
        mock_upload_to_bitrix,
    ):
        mock_get_deal_data.return_value = (
            {
                "ID": "777",
                "ASSIGNED_BY_ID": "42",
                "UF_CRM_1754380684375": "Иван Иванов",
            },
            None,
        )
        mock_get_user_with_photo.return_value = {
            "NAME": "Менеджер",
            "LAST_NAME": "Тестовый",
            "PHOTO_URL": "https://example.com/photo.jpg",
        }
        mock_get_pm_rate.return_value = None
        mock_calculate_km.return_value = {"result": 0}
        mock_generate_pdf.return_value = b"%PDF-1.4 test"
        mock_upload_to_bitrix.return_value = {"status": "success"}

        response = self.client.post(
            reverse("pdf"),
            {"document_id[2]": "DEAL_777"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        mock_generate_pdf.assert_called_once()
        payload = mock_generate_pdf.call_args.args[0]
        self.assertEqual(payload["document"]["generated_at"], str(payload["document"]["generated_at"]))
