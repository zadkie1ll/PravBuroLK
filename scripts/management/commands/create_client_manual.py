import requests
from django.core.management.base import BaseCommand, CommandError

from payments.client_onboarding import ClientOnboardingError, create_client_from_deal

BITRIX_WEBHOOK_URL = "https://prav-buro.bitrix24.ru/rest/24/pa1x5irnfpbcnh27/"


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
        "Создаёт клиента+договор для одной конкретной сделки с логином/паролем, заданными "
        "вручную (вместо автогенерации из телефона контакта). Пишет креды в Bitrix, как обычно."
    )

    def add_arguments(self, parser):
        parser.add_argument("--deal-id", required=True, help="ID сделки в Bitrix")
        parser.add_argument("--username", required=True, help="Логин клиента (обычно телефон, но можно любой)")
        parser.add_argument("--password", required=True, help="Пароль клиента")

    def handle(self, *args, **options):
        deal_id = options["deal_id"]
        username = options["username"]
        password = options["password"]

        self.stdout.write(self.style.NOTICE(f"Загружаем сделку {deal_id} из Bitrix..."))
        try:
            deal_data = _fetch_full_deal(deal_id)
        except Exception as exc:
            raise CommandError(f"Не удалось загрузить сделку: {exc}")

        if not deal_data:
            raise CommandError("Сделка не найдена или пустой ответ от Bitrix")

        try:
            result = create_client_from_deal(deal_data, username_override=username, password_override=password)
        except ClientOnboardingError as exc:
            raise CommandError(str(exc))

        self.stdout.write(
            self.style.SUCCESS(
                f"OK  deal={deal_id} -> client={result['client_id']} "
                f"username={result['username']} password={password}"
            )
        )
