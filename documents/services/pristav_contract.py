# documents/services/pristav_contract.py

import base64
import os
from datetime import datetime

import requests
from docx import Document

from documents.services.docx_utils import replace_text_preserving_format
from documents.views import WEBHOOK_URL

PRISTAV_CONTRACT_FIELD = "UF_CRM_1787841432134"  # Договор об оказании юридеческих услуг (file)
PRISTAV_SERVICE_NAME_FIELD = "UF_CRM_1787841397747"  # Наименование услуг (string)


def generate_pristav_contract(data, template_path, output_path):
    data["today"] = datetime.now().strftime("%d.%m.%Y")

    fio_parts = data.get("ФИО", "").split()
    if len(fio_parts) < 3:
        raise ValueError(f"ФИО должно содержать минимум 3 части (Фамилия Имя Отчество), получили: {data.get('ФИО')}")

    if not os.path.exists(template_path):
        raise FileNotFoundError(f"Template not found: {template_path}")

    doc = Document(template_path)
    replace_text_preserving_format(doc, data)
    doc.save(output_path)


def upload_pristav_contract_to_bitrix(deal_id, file_path, field_id):
    """Заливает договор в выделенное под него поле сделки Bitrix."""
    if not os.path.exists(file_path):
        return {"status": "error", "message": f"Файл не найден: {file_path}"}

    with open(file_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")

    payload = {
        "id": deal_id,
        "fields": {field_id: {"fileData": [os.path.basename(file_path), encoded]}},
    }

    url = f"{WEBHOOK_URL.rstrip('/')}/crm.deal.update.json"
    response = requests.post(url, json=payload)

    try:
        result = response.json()
    except Exception:
        return {"status": "error", "message": "Bitrix вернул не-JSON", "raw": response.text}

    if result.get("error"):
        return {
            "status": "error",
            "message": result.get("error_description", "Ошибка Bitrix"),
            "details": result,
        }

    return {"status": "success", "message": "Файл загружен"}
