import requests
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from payments.client_onboarding import CREDENTIALS_FIELD, generate_password

BITRIX_WEBHOOK_URL = "https://prav-buro.bitrix24.ru/rest/24/pa1x5irnfpbcnh27/"
CONTACT_WEBHOOK_URL = "https://prav-buro.bitrix24.ru/rest/24/vszzr53045oedn5m/"


class Command(BaseCommand):
    help = (
        "Обновляет логин/пароль уже существующего клиента и перезаписывает креды обратно "
        "в сделку в Bitrix. По умолчанию логин берётся из телефона контакта в Bitrix (после "
        "того как ты поправил его руками) — но можно задать --username/--password вручную, "
        "тогда в Bitrix вообще не лезем за телефоном. НЕ создаёт нового клиента, только "
        "обновляет существующего."
    )

    def add_arguments(self, parser):
        parser.add_argument("--client-id", required=True, type=int, help="ID клиента (Client.id) в нашей БД")
        parser.add_argument("--username", default=None, help="Задать логин вручную вместо телефона из Bitrix")
        parser.add_argument("--password", default=None, help="Задать пароль вручную вместо автогенерации")

    def handle(self, *args, **options):
        from clients.models import Client

        try:
            client = Client.objects.select_related("user").get(id=options["client_id"])
        except Client.DoesNotExist:
            raise CommandError(f"Client {options['client_id']} не найден")

        manual_username = options["username"]

        if manual_username:
            new_username = manual_username
        else:
            if not client.bitrix_id:
                raise CommandError(
                    "У клиента не заполнен bitrix_id — не знаю, какую сделку смотреть в Bitrix "
                    "(либо задай --username вручную)"
                )

            self.stdout.write(self.style.NOTICE(f"Загружаем сделку {client.bitrix_id}..."))
            deal_resp = requests.get(
                BITRIX_WEBHOOK_URL + "crm.deal.get.json", params={"ID": client.bitrix_id}, timeout=30
            )
            deal_resp.raise_for_status()
            deal_data = deal_resp.json().get("result") or {}
            if not deal_data:
                raise CommandError("Сделка не найдена в Bitrix")

            contact_id = deal_data.get("CONTACT_ID")
            if not contact_id:
                raise CommandError("У сделки нет CONTACT_ID")

            contact_resp = requests.get(
                CONTACT_WEBHOOK_URL + "crm.contact.get.json", params={"ID": contact_id}, timeout=30
            )
            contact_resp.raise_for_status()
            contact_data = contact_resp.json().get("result") or {}
            phones = contact_data.get("PHONE") or []
            new_username = phones[0]["VALUE"] if phones and phones[0].get("VALUE") else None
            if not new_username:
                raise CommandError("У контакта в Bitrix по-прежнему не заполнен телефон (или задай --username вручную)")

        if new_username == client.user.username:
            self.stdout.write(
                self.style.WARNING(f"Логин не изменился ({new_username}) — нечего обновлять.")
            )
            return

        if User.objects.filter(username=new_username).exclude(id=client.user.id).exists():
            raise CommandError(
                f"Логин {new_username} уже занят другим пользователем — сначала разберись с тем конфликтом"
            )

        new_password = options["password"] or generate_password()

        with transaction.atomic():
            client.user.username = new_username
            client.user.set_password(new_password)
            client.user.save(update_fields=["username", "password"])

            auth_text = f"{new_username}\n{new_password}"
            update_resp = requests.post(
                BITRIX_WEBHOOK_URL + "crm.deal.update.json",
                json={"id": client.bitrix_id, "fields": {CREDENTIALS_FIELD: auth_text}},
                timeout=30,
            )
            resp_data = update_resp.json()
            if resp_data.get("error"):
                raise CommandError(
                    f"Логин обновлён в БД, но запись в Bitrix не прошла: "
                    f"{resp_data.get('error_description', resp_data.get('error'))}"
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"OK client={client.id} deal={client.bitrix_id}: новый логин={new_username} пароль={new_password}"
            )
        )
