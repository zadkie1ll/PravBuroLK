from __future__ import annotations

import base64
import os
from typing import Any

from ..config import settings
from .bitrix_gateway_client import BitrixClient


def get_deal_data(deal_id: str) -> dict[str, Any]:
    client = BitrixClient()
    result = client.call("crm.deal.get", {"ID": deal_id})
    if not result:
        raise RuntimeError("Deal not found")
    return result


def get_phone_number(contact_id: str | int) -> str:
    client = BitrixClient()
    result = client.call("crm.contact.get", {"ID": contact_id}) or {}
    phone_list = result.get("PHONE") or []
    if phone_list:
        return phone_list[0].get("VALUE", "")
    return ""


def upload_to_bitrix(deal_id: str, file_path: str, field_id: str, payment_table: list[list[Any]]) -> dict[str, Any]:
    if not os.path.exists(file_path):
        return {"status": "error", "message": f"Файл не найден: {file_path}"}

    with open(file_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")

    try:
        second_payment = payment_table[1][2]
    except Exception:
        second_payment = None

    fields: dict[str, Any] = {field_id: {"fileData": [os.path.basename(file_path), encoded]}}
    if second_payment is not None:
        fields[settings.contract_second_payment_field] = second_payment

    client = BitrixClient()
    client.call("crm.deal.update", {"id": deal_id, "fields": fields})
    return {"status": "success", "message": "Файл загружен"}


def update_contract_link(deal_id: str, contract_url: str) -> None:
    client = BitrixClient()
    client.call(
        "crm.deal.update",
        {"id": deal_id, "fields": {settings.contract_link_field: contract_url}},
    )
