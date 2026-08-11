import re
from collections import defaultdict
from datetime import datetime

import openpyxl
import requests
from django.conf import settings
from django.core.management.base import BaseCommand

BITRIX_WEBHOOK_URL = "https://prav-buro.bitrix24.ru/rest/24/pa1x5irnfpbcnh27/"
CREDENTIALS_FIELD = "UF_CRM_1745888913952"


def _fetch_category_names() -> dict[str, str]:
    url = BITRIX_WEBHOOK_URL + "crm.dealcategory.list.json"
    response = requests.post(url, json={}, timeout=30)
    response.raise_for_status()
    data = response.json()
    if data.get("error"):
        raise RuntimeError(f"Bitrix error: {data.get('error_description', data.get('error'))}")
    return {str(item["ID"]): item.get("NAME", f"Категория {item['ID']}") for item in data.get("result", [])}


def _fetch_all_deals():
    """Постранично тянем все сделки портала (независимо от категории и от того,
    есть ли логин/пароль)."""
    deals = []
    start = 0
    while True:
        url = BITRIX_WEBHOOK_URL + "crm.deal.list.json"
        payload = {
            "select": ["ID", "TITLE", "STAGE_ID", "CATEGORY_ID", CREDENTIALS_FIELD],
            "start": start,
        }
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        if data.get("error"):
            raise RuntimeError(f"Bitrix error: {data.get('error_description', data.get('error'))}")

        deals.extend(data.get("result", []))

        next_start = data.get("next")
        if next_start is None:
            break
        start = next_start

    return deals


def _has_credentials(deal) -> bool:
    return bool(str(deal.get(CREDENTIALS_FIELD) or "").strip())


def _is_final_stage(stage_id: str) -> bool:
    """Bitrix-конвенция: финальные стадии воронки заканчиваются на :WON или :LOSE."""
    stage_id = (stage_id or "").upper()
    return stage_id.endswith(":WON") or stage_id.endswith(":LOSE")


def _safe_filename(name: str) -> str:
    return re.sub(r"[^\w\-]+", "_", name, flags=re.UNICODE).strip("_") or "bez_nazvaniya"


def _write_sheet(workbook, title, deals, include_credentials):
    sheet = workbook.create_sheet(title=title)
    headers = ["ID сделки", "Название", "Стадия", "Категория"]
    if include_credentials:
        headers.append("Есть креды")
        headers.append("Логин/пароль")
    sheet.append(headers)

    for deal in deals:
        row = [deal.get("ID"), deal.get("TITLE", ""), deal.get("STAGE_ID", ""), deal.get("CATEGORY_ID", "")]
        if include_credentials:
            row.append("да" if _has_credentials(deal) else "НЕТ")
            row.append(deal.get(CREDENTIALS_FIELD, ""))
        sheet.append(row)

    for column_cells in sheet.columns:
        length = max(len(str(cell.value or "")) for cell in column_cells)
        sheet.column_dimensions[column_cells[0].column_letter].width = min(length + 2, 60)


class Command(BaseCommand):
    help = (
        "Выгружает сделки в Excel, отдельный файл на каждую категорию воронки Bitrix: "
        "активные (незавершённая стадия, ВСЕ — включая те, где логин/пароль клиента ещё "
        "не выдан) и завершённые (WON/LOSE, только с выданными кредами) на разных листах."
    )

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.NOTICE("Загружаем категории из Bitrix..."))
        category_names = _fetch_category_names()

        self.stdout.write(self.style.NOTICE("Загружаем сделки из Bitrix..."))
        deals = _fetch_all_deals()

        deals_by_category = defaultdict(list)
        for deal in deals:
            deals_by_category[str(deal.get("CATEGORY_ID") or "0")].append(deal)

        out_dir = settings.BASE_DIR / f"client_credentials_audit_{datetime.now():%Y%m%d_%H%M%S}"
        out_dir.mkdir(parents=True, exist_ok=True)

        for category_id, category_deals in deals_by_category.items():
            category_name = category_names.get(category_id, f"Категория {category_id}")

            active = [d for d in category_deals if not _is_final_stage(d.get("STAGE_ID"))]
            finished = [
                d for d in category_deals if _is_final_stage(d.get("STAGE_ID")) and _has_credentials(d)
            ]
            missing_credentials = [d for d in active if not _has_credentials(d)]

            if not active and not finished:
                continue

            workbook = openpyxl.Workbook()
            workbook.remove(workbook.active)
            _write_sheet(workbook, "Активные", active, include_credentials=True)
            _write_sheet(workbook, "Завершённые", finished, include_credentials=False)

            filepath = out_dir / f"{_safe_filename(category_name)}.xlsx"
            workbook.save(filepath)

            self.stdout.write(self.style.WARNING(f"\n=== {category_name} (ID={category_id}) ==="))
            self.stdout.write(f"  Активных (не похуй): {len(active)}")
            self.stdout.write(self.style.ERROR(f"    из них БЕЗ кредов: {len(missing_credentials)}"))
            self.stdout.write(f"  Завершённых с выданными кредами (похуй): {len(finished)}")
            self.stdout.write(f"  Файл: {filepath}")

        self.stdout.write(self.style.SUCCESS(f"\nГотово. Все файлы в: {out_dir}"))
