from __future__ import annotations

import base64
import logging
import mimetypes
import re
import time
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from urllib.parse import quote, urlencode

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ..config import settings
from ..services import alfa_bank, bitrix_contract
from ..services.bitrix_gateway_client import BitrixClient
from ..services.django_signing import BadSignature, DjangoSigner
from ..services.docx_pipeline import calculate_payments, format_date, generate_contract
from ..services.signed_cookies import read_flags, write_flags

logger = logging.getLogger(__name__)
router = APIRouter(tags=["dogovor"])

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


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


def _validate_contract_token(deal_id: str, token: str | None) -> bool:
    if not token:
        return False
    try:
        return _contract_signer().unsign(token) == str(deal_id)
    except BadSignature:
        return False


def _build_contract_page_url(deal_id: str) -> str:
    token = _build_contract_token(deal_id)
    base_url = f"{settings.public_base_url}/dogovor/{deal_id}/"
    return f"{base_url}?token={quote(token)}"


def _build_contract_file_url(deal_id: str, token: str) -> str:
    return f"{settings.public_base_url}/dogovor/{deal_id}/document/?token={quote(token)}"


def _build_contract_payment_url(deal_id: str, token: str) -> str:
    return f"{settings.public_base_url}/dogovor/{deal_id}/pay/?token={quote(token)}"


def _build_contract_page_return_url(deal_id: str, token: str, payment_state: str | None = None) -> str:
    query = {"token": token}
    if payment_state:
        query["payment_state"] = payment_state
    return f"{settings.public_base_url}/dogovor/{deal_id}/?{urlencode(query)}"


def _build_office_preview_url(download_url: str | None) -> str | None:
    if not download_url:
        return None
    return f"https://view.officeapps.live.com/op/embed.aspx?src={quote(download_url, safe='')}"


def _get_generated_contract_path(deal_id: str) -> Path:
    return Path(settings.output_dir) / f"dogovor_{deal_id}.docx"


def _extract_file_id(file_value):
    if not file_value:
        return None
    if isinstance(file_value, dict):
        for key in ("id", "ID", "fileId", "FILE_ID"):
            if file_value.get(key):
                return _extract_file_id(file_value.get(key))
        return None
    if isinstance(file_value, (list, tuple)):
        for item in file_value:
            file_id = _extract_file_id(item)
            if file_id is not None:
                return file_id
        return None
    if isinstance(file_value, str):
        if file_value.startswith(("http://", "https://")):
            return file_value
        if file_value.isdigit():
            return int(file_value)
        return None
    if isinstance(file_value, int):
        return file_value
    return None


def _extract_file_url(file_value) -> str | None:
    if not file_value:
        return None
    if isinstance(file_value, dict):
        for key in ("url", "URL", "downloadUrl", "DOWNLOAD_URL", "showUrl", "SHOW_URL", "detailUrl", "DETAIL_URL", "src", "SRC"):
            value = file_value.get(key)
            if isinstance(value, str) and value.startswith(("http://", "https://")):
                return value
        for value in file_value.values():
            nested_url = _extract_file_url(value)
            if nested_url:
                return nested_url
        return None
    if isinstance(file_value, (list, tuple)):
        for item in file_value:
            nested_url = _extract_file_url(item)
            if nested_url:
                return nested_url
        return None
    if isinstance(file_value, str) and file_value.startswith(("http://", "https://")):
        return file_value
    return None


def _resolve_contract_download_url(file_value) -> str | None:
    direct_url = _extract_file_url(file_value)
    if direct_url:
        return direct_url

    file_id = _extract_file_id(file_value)
    if not file_id:
        return None
    if isinstance(file_id, str) and file_id.startswith(("http://", "https://")):
        return file_id

    try:
        result = BitrixClient().call("disk.file.get", {"id": file_id}) or {}
    except Exception:
        logger.exception("Failed to resolve Bitrix disk file URL for file_id=%s", file_id)
        return None
    return result.get("DOWNLOAD_URL") or result.get("DETAIL_URL") or result.get("SRC")


def _extract_decimal_amount(value) -> Decimal:
    if value in (None, "", False):
        return Decimal("0")
    if isinstance(value, (int, float, Decimal)):
        return Decimal(str(value))
    normalized = str(value).split("|")[0].strip().replace(" ", "").replace(",", ".")
    if not normalized:
        return Decimal("0")
    return Decimal(normalized)


def _format_amount_rub(amount: Decimal) -> str:
    normalized = amount.quantize(Decimal("1")) if amount == amount.to_integral_value() else amount.quantize(Decimal("0.01"))
    return f"{normalized:,.2f}".replace(",", " ").replace(".00", "")


def _get_contract_payment_purpose(deal_data: dict) -> str:
    client_name = (deal_data.get("TITLE") or "").strip()
    contract_number = (deal_data.get(settings.contract_number_field) or "").strip()
    if contract_number and client_name:
        return f"Оплата по договору {contract_number} {client_name}"
    if contract_number:
        return f"Оплата по договору {contract_number}"
    return f"Оплата по договору {client_name}".strip()


def _get_contract_payment_requisites() -> list[tuple[str, str]]:
    requisites = [
        ("Получатель", settings.contract_payment_recipient.strip()),
        ("Адрес", settings.contract_payment_address.strip()),
        ("ИНН", settings.contract_payment_inn.strip()),
        ("КПП", settings.contract_payment_kpp.strip()),
        ("Валюта", settings.contract_payment_currency.strip()),
        ("Банк", settings.contract_payment_bank.strip()),
        ("БИК", settings.contract_payment_bik.strip()),
        ("Расчетный счет", settings.contract_payment_account.strip()),
        ("Корреспондентский счет", settings.contract_payment_corr_account.strip()),
    ]
    return [(label, value) for label, value in requisites if value]


def _get_contract_payment_qr_data_uri() -> str:
    if not settings.contract_payment_qr_path:
        return ""
    image_path = Path(settings.contract_payment_qr_path)
    if not image_path.exists():
        return ""
    mime_type, _ = mimetypes.guess_type(image_path.name)
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:{mime_type or 'image/jpeg'};base64,{encoded}"


def _build_contract_payment_context(deal_id: str, token: str, deal_data: dict) -> dict:
    first_payment_amount = _extract_decimal_amount(deal_data.get(settings.contract_first_payment_field))
    return {
        "contract_payment_url": _build_contract_payment_url(deal_id, token),
        "first_payment_amount": _format_amount_rub(first_payment_amount),
        "payment_purpose": _get_contract_payment_purpose(deal_data),
        "payment_requisites": _get_contract_payment_requisites(),
        "payment_qr_data_uri": _get_contract_payment_qr_data_uri(),
    }


def _register_contract_payment(deal_id: str, token: str, deal_data: dict) -> str:
    amount = _extract_decimal_amount(deal_data.get(settings.contract_first_payment_field))
    if amount <= 0:
        raise RuntimeError("Сумма первого платежа не заполнена")
    order_number = f"contract-{deal_id}-{int(time.time())}"

    return alfa_bank.register_order(
        order_number=order_number,
        amount_kopecks=int((amount * 100).quantize(Decimal("1"))),
        description=_get_contract_payment_purpose(deal_data),
        return_url=f"{_build_contract_page_return_url(deal_id, token, 'success')}&orderNumber={quote(order_number)}",
        fail_url=f"{_build_contract_page_return_url(deal_id, token, 'failed')}&orderNumber={quote(order_number)}",
    )


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


def _cookie_name(deal_id: str) -> str:
    return f"contract_payment_{deal_id}"


@router.get("/dogovor/{deal_id}/")
@router.post("/dogovor/{deal_id}/")
async def contract_confirmation_page(request: Request, deal_id: int):
    token = request.query_params.get("token")
    if request.method == "POST" and not token:
        token = (await request.form()).get("token")
    if not _validate_contract_token(str(deal_id), token):
        return JSONResponse({"detail": "Страница договора не найдена"}, status_code=404)

    error_message = ""
    success_message = ""

    try:
        deal_data = bitrix_contract.get_deal_data(str(deal_id))
    except Exception as exc:
        logger.exception("Failed to load contract page for deal %s", deal_id)
        return templates.TemplateResponse(
            request,
            "contract_confirmation.html",
            {
                "deal_id": deal_id,
                "token": token,
                "error_message": f"Не удалось загрузить договор: {exc}",
                "contract_download_url": None,
                "contract_preview_url": None,
                "is_confirmed": False,
                "contract_number": "",
                "client_name": "",
            },
            status_code=502,
        )

    if request.method == "POST":
        form = await request.form()
        if form.get("agree") != "on":
            error_message = "Для подтверждения нужно отметить согласие с договором."
        else:
            try:
                bitrix_contract.update_contract_confirmation(str(deal_id), accepted=True)
                success_message = "Договор подтвержден."
                deal_data[settings.contract_accepted_field] = 1
            except Exception as exc:
                logger.exception("Failed to confirm contract for deal %s", deal_id)
                error_message = f"Не удалось сохранить подтверждение: {exc}"

    generated_contract_path = _get_generated_contract_path(str(deal_id))
    if generated_contract_path.exists():
        contract_download_url = _build_contract_file_url(str(deal_id), token)
    else:
        contract_download_url = _resolve_contract_download_url(deal_data.get(settings.contract_file_field))
    if not contract_download_url and not error_message:
        error_message = "Не удалось получить прямую ссылку на файл договора. Подтверждение остается доступным."
    contract_preview_url = _build_office_preview_url(contract_download_url)
    is_confirmed = str(deal_data.get(settings.contract_accepted_field)).upper() in {"1", "Y", "TRUE"}

    payment_state = (request.query_params.get("payment_state") or "").strip().lower()
    payment_error = (request.query_params.get("payment_error") or "").strip()
    payment_order_number = (request.query_params.get("orderNumber") or "").strip()

    flags = read_flags(request.cookies.get(_cookie_name(str(deal_id))))
    is_payment_completed = bool(flags.get("completed"))

    if payment_state == "success":
        is_payment_completed = True
        flags["completed"] = True

        if payment_order_number and flags.get("logged_order") != payment_order_number:
            try:
                amount = _extract_decimal_amount(deal_data.get(settings.contract_first_payment_field))
                bitrix_contract.add_contract_payment_timeline_comment(
                    str(deal_id),
                    payment_order_number,
                    (
                        "Поступила успешная оплата по договору\n"
                        f"Сумма: {_format_amount_rub(amount)} ₽\n"
                        f"Номер платежа: {payment_order_number}"
                    ),
                )
                flags["logged_order"] = payment_order_number
            except Exception as exc:
                logger.exception("Failed to add contract payment timeline comment for deal %s", deal_id)
                if not payment_error:
                    payment_error = f"Не удалось записать оплату в журнал: {exc}"

    payment_context = _build_contract_payment_context(str(deal_id), token, deal_data)

    response = templates.TemplateResponse(
        request,
        "contract_confirmation.html",
        {
            "deal_id": deal_id,
            "token": token,
            "error_message": error_message,
            "success_message": success_message,
            "contract_download_url": contract_download_url,
            "contract_preview_url": contract_preview_url,
            "is_confirmed": is_confirmed,
            "contract_number": deal_data.get(settings.contract_number_field, ""),
            "client_name": deal_data.get("TITLE", ""),
            "payment_state": payment_state,
            "payment_error": payment_error,
            "is_payment_completed": is_payment_completed,
            **payment_context,
        },
    )
    response.set_cookie(_cookie_name(str(deal_id)), write_flags(flags), httponly=True, max_age=60 * 60 * 24 * 30)
    return response


@router.get("/dogovor/{deal_id}/document/")
def contract_document_file(deal_id: int, token: str | None = None):
    if not _validate_contract_token(str(deal_id), token):
        return JSONResponse({"detail": "Файл договора не найден"}, status_code=404)

    contract_path = _get_generated_contract_path(str(deal_id))
    if not contract_path.exists():
        return JSONResponse({"detail": "Файл договора не найден"}, status_code=404)

    return FileResponse(
        contract_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=contract_path.name,
    )


@router.get("/dogovor/{deal_id}/pay/")
def contract_payment_redirect(deal_id: int, token: str | None = None):
    if not _validate_contract_token(str(deal_id), token):
        return JSONResponse({"detail": "Страница оплаты не найдена"}, status_code=404)

    try:
        deal_data = bitrix_contract.get_deal_data(str(deal_id))
        form_url = _register_contract_payment(str(deal_id), token, deal_data)
    except Exception as exc:
        logger.exception("Failed to create contract payment for deal %s", deal_id)
        error_query = urlencode({"token": token, "payment_state": "error", "payment_error": str(exc)})
        return RedirectResponse(f"/dogovor/{deal_id}/?{error_query}", status_code=302)

    return RedirectResponse(form_url, status_code=302)
