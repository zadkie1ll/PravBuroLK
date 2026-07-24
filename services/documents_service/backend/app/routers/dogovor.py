from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..config import settings
from ..services import bitrix_contract
from ..services.django_signing import DjangoSigner
from ..services.docx_pipeline import calculate_payments, format_date, generate_contract

logger = logging.getLogger(__name__)
router = APIRouter(tags=["dogovor"])


def _extract_deal_id(post_data: dict) -> str | None:
    document_id_2 = post_data.get("document_id[2]")
    if not document_id_2:
        return None
    match = re.search(r"DEAL_(\d+)", document_id_2)
    if not match:
        return None
    return match.group(1)


def _contract_signer() -> DjangoSigner:
    return DjangoSigner(key=settings.django_secret_key, salt=settings.contract_page_sign_salt)


def _build_contract_token(deal_id: str) -> str:
    return _contract_signer().sign(deal_id)


def _build_contract_page_url(deal_id: str) -> str:
    token = _build_contract_token(deal_id)
    base_url = f"{settings.monolith_base_url}/dogovor/{deal_id}/"
    return f"{base_url}?token={quote(token)}"


def _get_generated_contract_path(deal_id: str) -> Path:
    return Path(settings.output_dir) / f"dogovor_{deal_id}.docx"


@router.post("/dogovor")
async def dogovor(request: Request):
    content_type = (request.headers.get("content-type") or "").lower()
    if "application/json" in content_type:
        post_data = dict(await request.json())
    else:
        post_data = dict(await request.form())

    logger.info("INCOMING POST: %s", post_data)

    deal_id = _extract_deal_id(post_data)
    if not deal_id:
        return JSONResponse({"status": "error", "message": "Invalid deal ID"}, status_code=400)

    try:
        deal_data = bitrix_contract.get_deal_data(deal_id)
    except Exception as exc:
        return JSONResponse({"status": "error", "message": f"Deal fetch error: {exc}"}, status_code=500)

    try:
        contact_id = deal_data.get("CONTACT_ID")
        phone_number = bitrix_contract.get_phone_number(contact_id) if contact_id else "00000000000"

        fio = deal_data.get("TITLE", "")
        fio_parts = fio.split()
        last_name = fio_parts[0] if len(fio_parts) > 0 else ""
        first_name = fio_parts[1] if len(fio_parts) > 1 else ""
        mid_name = fio_parts[2] if len(fio_parts) > 2 else ""

        contract = {
            "номер договора": deal_data.get("UF_CRM_1745892727271", "000"),
            "ФИО": fio,
            "фамилия": last_name,
            "имя": first_name,
            "отчество": mid_name,
            "дата рождения": format_date(deal_data.get("UF_CRM_1745888327609")),
            "серия": deal_data.get("UF_CRM_1745889060779", ""),
            "номер": deal_data.get("UF_CRM_1745889067225", ""),
            "кем": deal_data.get("UF_CRM_1745889085935", ""),
            "дата выдачи": format_date(deal_data.get("UF_CRM_1754384630146")),
            "код": deal_data.get("UF_CRM_1745889094660", ""),
            "место рождения": deal_data.get("UF_CRM_1745889105838", ""),
            "адрес регистрации": deal_data.get("UF_CRM_1745893079148", ""),
            "номер телефона": phone_number,
            "сумма юристы": str(int(float(deal_data.get("OPPORTUNITY", 0)))),
            "сумма бонус": deal_data.get("UF_CRM_1742457114242", "0").split("|")[0],
            "Первый платеж": deal_data.get("UF_CRM_1742468532579", "0").split("|")[0],
            "today": datetime.today().strftime("%d.%m.%Y"),
            "data": datetime.today().strftime("%m/%Y"),
            "количество платежей": deal_data.get("UF_CRM_1742480133860", "1"),
            "скидка": deal_data.get("UF_CRM_1742457148727", "0").split("|")[0],
            "дата начала платежей": format_date(deal_data.get("UF_CRM_1742468566169")),
            "Число для оплаты": deal_data.get("UF_CRM_1745893194511", "1"),
        }
    except Exception as exc:
        return JSONResponse({"status": "error", "message": f"Data preparation error: {exc}"}, status_code=500)

    try:
        total = int(contract["сумма юристы"]) + int(contract["сумма бонус"])
        num = int(contract["количество платежей"])
        first = int(contract["Первый платеж"])
        discount = int(contract["скидка"])
        start_date = contract["дата начала платежей"]
        second_day = contract["Число для оплаты"]

        payments = calculate_payments(num, total, discount, start_date, first, second_payment_day=second_day)
    except Exception as exc:
        return JSONResponse({"status": "error", "message": f"Payment calc error: {exc}"}, status_code=500)

    template = Path(settings.template_path)
    output = _get_generated_contract_path(deal_id)

    if not template.exists():
        return JSONResponse({"status": "error", "message": f"Template not found: {template}"}, status_code=500)

    try:
        generate_contract(contract, str(template), str(output), payments)
    except Exception as exc:
        return JSONResponse({"status": "error", "message": f"Doc generation error: {exc}"}, status_code=500)

    try:
        bitrix_contract.upload_to_bitrix(deal_id, str(output), settings.contract_file_field, payments)
    except Exception as exc:
        return JSONResponse({"status": "error", "message": f"Upload error: {exc}"}, status_code=500)

    confirmation_url = _build_contract_page_url(deal_id)

    try:
        bitrix_contract.update_contract_link(deal_id, confirmation_url)
    except Exception:
        logger.exception("Failed to save contract URL for deal %s", deal_id)

    return JSONResponse(
        {
            "status": "success",
            "message": "Document generated & uploaded",
            "deal_id": deal_id,
            "confirmation_url": confirmation_url,
        }
    )
