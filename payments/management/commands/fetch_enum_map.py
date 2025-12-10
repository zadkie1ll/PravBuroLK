import json
import requests
from django.core.management.base import BaseCommand, CommandError

BITRIX_WEBHOOK_URL = "https://prav-buro.bitrix24.ru/rest/24/pa1x5irnfpbcnh27/"


def get_userfield_internal_id(field_name: str) -> str:
    """
    Получает внутренний ID пользовательского поля по FIELD_NAME.
    """
    url = f"{BITRIX_WEBHOOK_URL}crm.deal.userfield.list"
    response = requests.get(url)
    
    try:
        data = response.json()
    except Exception:
        raise CommandError("Bitrix вернул невалидный JSON")

    if "result" not in data:
        raise CommandError(f"Bitrix error: {data}")

    for field in data["result"]:
        if field.get("FIELD_NAME") == field_name:
            return field["ID"]

    raise CommandError(f"Поле {field_name} не найдено в userfield.list")


def fetch_enum_map(field_name: str, save_to_file: str | None = None):
    """
    Получает словарь значений списка пользовательского поля.
    """
    internal_id = get_userfield_internal_id(field_name)

    url = f"{BITRIX_WEBHOOK_URL}crm.deal.userfield.get"
    response = requests.get(url, params={"ID": internal_id})

    try:
        data = response.json()
    except Exception:
        raise CommandError("Bitrix вернул невалидный JSON")

    if "result" not in data:
        raise CommandError(f"Bitrix error: {data}")

    field = data["result"]
    enum_list = field.get("LIST", [])

    mapping = {item["ID"]: item["VALUE"] for item in enum_list}

    if save_to_file:
        with open(save_to_file, "w", encoding="utf-8") as f:
            json.dump(mapping, f, ensure_ascii=False, indent=4)

    return mapping


class Command(BaseCommand):
    help = "Получает карту значений списочного пользовательского поля сделки Bitrix24"

    def add_arguments(self, parser):
        parser.add_argument(
            "--field",
            required=True,
            help="FIELD_NAME пользовательского поля, например UF_CRM_1745886887592"
        )
        parser.add_argument(
            "--save",
            required=False,
            help="Сохранить результат в JSON файл"
        )

    def handle(self, *args, **options):
        field_name = options["field"]
        save_path = options.get("save")

        self.stdout.write(self.style.WARNING(f"Получение данных для поля: {field_name}"))

        mapping = fetch_enum_map(field_name, save_to_file=save_path)

        self.stdout.write(self.style.SUCCESS("Готово!"))
        self.stdout.write(json.dumps(mapping, indent=4, ensure_ascii=False))
