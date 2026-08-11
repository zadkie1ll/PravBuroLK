"""Создание клиента+договора по данным сделки Bitrix + выдача логина/пароля в Bitrix.

Вынесено из BitrixCreateClientFromDealView.post() (payments/views.py), чтобы использовать
ту же логику и из веб-хука Bitrix, и из management-команды бэкфилла (backfill_client_credentials).
"""
from __future__ import annotations

import random
import re
import string
from datetime import datetime
from decimal import Decimal

import requests
from django.conf import settings
from django.db import transaction

CREDENTIALS_FIELD = "UF_CRM_1745888913952"


class ClientOnboardingError(Exception):
    pass


def generate_password(length: int = 8) -> str:
    """Генерация простого пароля"""
    chars = string.ascii_letters + string.digits
    return "".join(random.choice(chars) for _ in range(length))


def _safe_int(value, default=0):
    if value is None:
        return default
    s = str(value).split("|")[0].strip()
    s = s.replace(" ", "").replace(" ", "")
    m = re.search(r"-?\d+[\,\.\d]*", s)
    if not m:
        try:
            return int(s)
        except Exception:
            return default
    num = m.group(0).replace(",", ".")
    try:
        return int(float(num))
    except Exception:
        return default


def _parse_bitrix_date(value):
    if not value:
        return None
    s = str(value).strip()
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    except Exception:
        pass
    try:
        return datetime.fromisoformat(s).date()
    except Exception:
        return None


def _clean_text(value) -> str:
    return str(value or "").strip()


def _split_full_name(full_name):
    parts = [part for part in _clean_text(full_name).split() if part]
    if len(parts) >= 2:
        return parts[1], parts[0], " ".join(parts[2:])
    if len(parts) == 1:
        return parts[0], "", ""
    return "", "", ""


def create_client_from_deal(
    deal_data: dict, username_override: str | None = None, password_override: str | None = None
) -> dict:
    """Создаёт Client+Contract+InstallmentPlan по данным сделки Bitrix и пишет логин/пароль
    обратно в поле сделки. Бросает ClientOnboardingError с понятным текстом при любой проблеме.
    Оборачивать в transaction.atomic не нужно — уже сделано внутри.

    username_override/password_override — задать логин/пароль вручную вместо автогенерации
    (телефон контакта / случайная строка). При заданном username_override телефон контакта
    всё равно используется как fallback для имени/фамилии, но не для логина."""
    from clients.services import ClientService

    BITRIX_WEBHOOK = settings.BITRIX_WEBHOOK_URL.rstrip("/") + "/"

    first_name = _clean_text(deal_data.get("UF_CRM_1754380684375"))
    last_name = _clean_text(deal_data.get("UF_CRM_1754380678904"))
    middlename = _clean_text(deal_data.get("UF_CRM_1754380692399"))

    total_amount = _safe_int(deal_data.get("OPPORTUNITY"))
    discount = _safe_int(deal_data.get("UF_CRM_1742457148727"))
    bonus = _safe_int(deal_data.get("UF_CRM_1742457114242"))
    first_payment = _safe_int(deal_data.get("UF_CRM_1742468532579"))
    number_of_payments = _safe_int(deal_data.get("UF_CRM_1742480133860"))
    preferred_payment_day = _safe_int(deal_data.get("UF_CRM_1745893194511"))

    total_with_bonus = max(total_amount - discount + bonus, 0)

    external_id = deal_data.get("CONTACT_ID")
    contact_data = {}

    if username_override:
        # Ручное создание — контакт нужен только как источник имени/фамилии (best-effort),
        # логин задан явно, поэтому отсутствие/недоступность контакта не блокирует создание.
        username = username_override
        if external_id:
            contact_url = f"https://prav-buro.bitrix24.ru/rest/24/vszzr53045oedn5m/crm.contact.get.json?ID={external_id}"
            try:
                contact_resp = requests.get(contact_url, timeout=30)
                if contact_resp.status_code == 200:
                    contact_data = contact_resp.json().get("result") or {}
            except requests.RequestException:
                contact_data = {}
    else:
        # Автоматическое создание — контакт обязателен, логин = его телефон.
        if not external_id:
            raise ClientOnboardingError("CONTACT_ID not found")

        contact_url = f"https://prav-buro.bitrix24.ru/rest/24/vszzr53045oedn5m/crm.contact.get.json?ID={external_id}"
        contact_resp = requests.get(contact_url, timeout=30)
        if contact_resp.status_code != 200:
            raise ClientOnboardingError(f"Failed to fetch contact (status={contact_resp.status_code})")

        contact_data = contact_resp.json().get("result") or {}
        username = (contact_data.get("PHONE") or [{}])[0].get("VALUE")
        if not username:
            raise ClientOnboardingError("Phone number not found")

    if not first_name:
        first_name = _clean_text(contact_data.get("NAME"))
    if not last_name:
        last_name = _clean_text(contact_data.get("LAST_NAME"))
    if not middlename:
        middlename = _clean_text(contact_data.get("SECOND_NAME"))

    title_first_name, title_last_name, title_middlename = _split_full_name(deal_data.get("TITLE"))
    if not first_name:
        first_name = title_first_name
    if not last_name:
        last_name = title_last_name
    if not middlename:
        middlename = title_middlename

    if not (first_name and last_name):
        raise ClientOnboardingError(
            "Имя и фамилия обязательны — не удалось получить их из полей сделки, контакта или названия сделки"
        )

    new_password = password_override or generate_password()
    acquiring_flag = str(deal_data.get("UF_CRM_1760099004")) == "2022"

    with transaction.atomic():
        from payments.views import build_withdrawals_bitrix_fields

        client, contract, plan = ClientService.create_client_with_contract(
            username=username,
            password=new_password,
            name=first_name,
            surname=last_name,
            middlename=middlename,
            email="client@prav-buro.ru",
            bitrix_id=str(deal_data.get("ID") or ""),
            stage="1",
            total_amount=total_with_bonus,
            discount=discount,
            first_payment=first_payment,
            first_payment_date=_parse_bitrix_date(deal_data.get("UF_CRM_1742468566169")),
            number_of_payments=number_of_payments,
            preferred_payment_day=preferred_payment_day,
            acquiring_enabled=acquiring_flag,
        )

        deal_id = str(deal_data.get("ID") or "")
        bitrix_url = f"{BITRIX_WEBHOOK}crm.deal.update.json"
        auth_text = f"{username}\n{new_password}"

        payload = {
            "id": deal_id,
            "fields": {
                CREDENTIALS_FIELD: auth_text,
                **build_withdrawals_bitrix_fields(client),
            },
        }

        response = requests.post(bitrix_url, json=payload, timeout=30)
        resp_data = response.json()
        if resp_data.get("error"):
            raise ClientOnboardingError(
                f"Bitrix error: {resp_data.get('error_description', resp_data.get('error'))}"
            )

    return {
        "client_id": client.id,
        "contract_id": contract.id,
        "plan_id": plan.id,
        "username": client.user.username,
        "password": new_password,
        "bitrix_deal_id": deal_data.get("ID"),
    }
