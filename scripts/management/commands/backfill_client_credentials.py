import requests
from django.core.management.base import BaseCommand

from payments.client_onboarding import ClientOnboardingError, create_client_from_deal

BITRIX_WEBHOOK_URL = "https://prav-buro.bitrix24.ru/rest/24/pa1x5irnfpbcnh27/"
CREDENTIALS_FIELD = "UF_CRM_1745888913952"
SUPPORT_CATEGORY_ID = 2  # см. pravburo/settings.py:329 DEAL_DUPLICATION_SOURCE_CATEGORY_ID


def _fetch_active_deals_without_credentials():
    deals = []
    start = 0
    while True:
        url = BITRIX_WEBHOOK_URL + "crm.deal.list.json"
        payload = {
            "filter": {"CATEGORY_ID": SUPPORT_CATEGORY_ID},
            "select": ["ID", "TITLE", "STAGE_ID", CREDENTIALS_FIELD],
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


def _fetch_full_deal(deal_id: str) -> dict:
    url = BITRIX_WEBHOOK_URL + "crm.deal.get.json"
    response = requests.get(url, params={"ID": deal_id}, timeout=30)
    response.raise_for_status()
    data = response.json()
    if data.get("error"):
        raise RuntimeError(f"Bitrix error: {data.get('error_description', data.get('error'))}")
    return data.get("result") or {}


class Command(BaseCommand):
    help = (
        "Бэкфилл: находит активные сделки категории 'Отдел сопровождения' без выданного "
        "логина/пароля клиента и создаёт для них личный кабинет (Client+Contract+InstallmentPlan) "
        "+ пишет креды обратно в Bitrix — та же логика, что у обычного webhook-создания клиента. "
        "БЕЗ --execute только показывает список, ничего не создаёт и не пишет в Bitrix."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--execute",
            action="store_true",
            help="Реально создать клиентов и записать креды в Bitrix (без этого флага — только dry-run)",
        )
        parser.add_argument(
            "--deal-id",
            action="append",
            default=None,
            help="Ограничиться конкретными ID сделок (можно указать несколько раз). "
            "Без этого флага — все подходящие сделки категории.",
        )

    def handle(self, *args, **options):
        execute = options["execute"]
        only_deal_ids = set(options["deal_id"]) if options["deal_id"] else None

        self.stdout.write(self.style.NOTICE("Ищем активные сделки без кредов..."))
        deals = _fetch_active_deals_without_credentials()

        if only_deal_ids:
            deals = [d for d in deals if str(d.get("ID")) in only_deal_ids]

        if not deals:
            self.stdout.write(self.style.SUCCESS("Ничего не найдено — все активные сделки уже с кредами."))
            return

        self.stdout.write(f"Найдено {len(deals)} сделок без кредов:")
        for deal in deals:
            self.stdout.write(f"  ID={deal['ID']} | {deal.get('TITLE', '')} | стадия={deal.get('STAGE_ID')}")

        if not execute:
            self.stdout.write(
                self.style.WARNING(
                    "\nЭто был DRY-RUN — ничего не создано и не записано в Bitrix. "
                    "Запусти с --execute, чтобы реально создать клиентов."
                )
            )
            return

        self.stdout.write(self.style.WARNING(f"\n--execute передан, создаём {len(deals)} клиентов..."))

        succeeded, failed = [], []
        for deal in deals:
            deal_id = str(deal["ID"])
            try:
                full_deal_data = _fetch_full_deal(deal_id)
                result = create_client_from_deal(full_deal_data)
                succeeded.append((deal_id, result))
                self.stdout.write(
                    self.style.SUCCESS(f"  OK  deal={deal_id} -> client={result['client_id']} username={result['username']}")
                )
            except ClientOnboardingError as exc:
                failed.append((deal_id, str(exc)))
                self.stdout.write(self.style.ERROR(f"  FAIL deal={deal_id}: {exc}"))
            except Exception as exc:  # noqa: BLE001 — бэкфилл не должен падать целиком из-за одной сделки
                failed.append((deal_id, str(exc)))
                self.stdout.write(self.style.ERROR(f"  FAIL deal={deal_id}: {exc}"))

        self.stdout.write(f"\nГотово: {len(succeeded)} успешно, {len(failed)} с ошибкой.")
