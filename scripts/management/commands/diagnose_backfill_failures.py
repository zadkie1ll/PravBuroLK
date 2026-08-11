from datetime import datetime
from decimal import Decimal

import openpyxl
import requests
from django.conf import settings
from django.core.management.base import BaseCommand

BITRIX_WEBHOOK_URL = "https://prav-buro.bitrix24.ru/rest/24/pa1x5irnfpbcnh27/"
CONTACT_WEBHOOK_URL = "https://prav-buro.bitrix24.ru/rest/24/vszzr53045oedn5m/"
CREDENTIALS_FIELD = "UF_CRM_1745888913952"
SUPPORT_CATEGORY_ID = 2


def _fetch_active_deals_without_credentials():
    deals = []
    start = 0
    while True:
        url = BITRIX_WEBHOOK_URL + "crm.deal.list.json"
        payload = {
            "filter": {"CATEGORY_ID": SUPPORT_CATEGORY_ID},
            "select": ["ID", "TITLE", "STAGE_ID", "CONTACT_ID", "OPPORTUNITY", CREDENTIALS_FIELD],
            "start": start,
        }
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        if data.get("error"):
            raise RuntimeError(f"Bitrix error: {data.get('error_description', data.get('error'))}")

        for deal in data.get("result", []):
            stage = str(deal.get("STAGE_ID") or "").upper()
            has_credentials = bool(str(deal.get(CREDENTIALS_FIELD) or "").strip())
            is_final = stage.endswith(":WON") or stage.endswith(":LOSE")
            if not is_final and not has_credentials:
                deals.append(deal)

        next_start = data.get("next")
        if next_start is None:
            break
        start = next_start

    return deals


def _diagnose(deal: dict) -> str:
    """Та же цепочка проверок, что в create_client_from_deal, но только чтение — без записи."""
    from clients.models import Client

    deal_id = str(deal.get("ID") or "")

    contact_id = deal.get("CONTACT_ID")
    if not contact_id:
        return "CONTACT_ID not found — у сделки нет привязанного контакта"

    try:
        contact_resp = requests.get(
            f"{CONTACT_WEBHOOK_URL}crm.contact.get.json", params={"ID": contact_id}, timeout=30
        )
    except requests.RequestException as exc:
        return f"Сетевая ошибка при запросе контакта: {exc}"

    if contact_resp.status_code != 200:
        return f"Контакт не читается (status={contact_resp.status_code}) — вероятно, контакт удалён/объединён/битый"

    contact_json = contact_resp.json()
    if contact_json.get("error"):
        return f"Bitrix отказал в контакте: {contact_json.get('error_description', contact_json.get('error'))}"

    contact_data = contact_json.get("result") or {}
    phones = contact_data.get("PHONE") or []
    if not phones or not phones[0].get("VALUE"):
        return "У контакта не заполнен номер телефона"

    username = phones[0]["VALUE"]
    if Client.objects.filter(bitrix_id=deal_id).exists():
        return "У этой сделки уже есть Client с таким bitrix_id (создан ранее иначе)"

    try:
        opportunity = Decimal(str(deal.get("OPPORTUNITY") or 0))
    except Exception:
        opportunity = Decimal(0)
    if opportunity <= 0:
        return "OPPORTUNITY (общая сумма) не заполнена или равна 0"

    return "OK — видимых проблем нет, должно создаться нормально"


class Command(BaseCommand):
    help = (
        "Для активных сделок 'Отдел сопровождения' без кредов проверяет (read-only, без "
        "создания клиентов), почему именно backfill_client_credentials не смог бы их создать. "
        "Пишет результат в Excel — по одной понятной причине на строку."
    )

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.NOTICE("Ищем активные сделки без кредов..."))
        deals = _fetch_active_deals_without_credentials()
        self.stdout.write(f"Найдено {len(deals)} сделок, проверяем каждую...")

        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.title = "Диагностика"
        sheet.append(["Deal ID", "Название", "Стадия", "Причина"])

        for i, deal in enumerate(deals, 1):
            reason = _diagnose(deal)
            sheet.append([deal.get("ID"), deal.get("TITLE", ""), deal.get("STAGE_ID", ""), reason])
            self.stdout.write(f"  [{i}/{len(deals)}] deal={deal.get('ID')}: {reason}")

        for column_cells in sheet.columns:
            length = max(len(str(cell.value or "")) for cell in column_cells)
            sheet.column_dimensions[column_cells[0].column_letter].width = min(length + 2, 80)

        filepath = settings.BASE_DIR / f"backfill_diagnosis_{datetime.now():%Y%m%d_%H%M%S}.xlsx"
        workbook.save(filepath)
        self.stdout.write(self.style.SUCCESS(f"\nФайл сохранён: {filepath}"))
