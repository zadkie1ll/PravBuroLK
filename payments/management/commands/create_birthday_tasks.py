import requests
import openpyxl
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand

BITRIX_WEBHOOK_URL = "https://prav-buro.bitrix24.ru/rest/24/pa1x5irnfpbcnh27/"
ACCOMPLICE_ID = 58
EXCEL_FILENAME = "deals_export.xlsx"
CREATOR_ID = 290


def get_deal_responsible_id(deal_id):
    """
    Возвращает ID ответственного по сделке
    """
    url = BITRIX_WEBHOOK_URL + "crm.deal.get.json"
    response = requests.get(url, params={"id": deal_id}).json()

    if "result" in response and response["result"]:
        return int(response["result"].get("ASSIGNED_BY_ID"))

    return None


def create_task_for_birthday(deal_id, client_name, birthday_date):
    """
    Создает задачу в Bitrix24 для поздравления с днем рождения
    """

    responsible_id = get_deal_responsible_id(deal_id)

    if not responsible_id:
        responsible_id = ACCOMPLICE_ID

    task_title = f"Поздравить {client_name} с днём рождения"
    description = f"Клиент празднует ДР {birthday_date.strftime('%d.%m.%Y')}"

    deadline = birthday_date.strftime("%Y-%m-%d") + " 12:00:00"

    payload = {
        "fields": {
            "TITLE": task_title,
            "DESCRIPTION": description,
            "CREATED_BY": CREATOR_ID,
            "RESPONSIBLE_ID": responsible_id,
            "ACCOMPLICES": [ACCOMPLICE_ID],       
            "DEADLINE": deadline,
            "UF_CRM_TASK": [f"D_{deal_id}"],      
        }
    }

    url = BITRIX_WEBHOOK_URL + "tasks.task.add.json"
    response = requests.post(url, json=payload)

    return response.json()


def read_deals_from_excel(filename):
    """
    Читает Excel и возвращает список клиентов: {deal_id, name, birthdate}
    """
    workbook = openpyxl.load_workbook(filename)
    sheet = workbook.active

    results = []

    for row in sheet.iter_rows(min_row=2, values_only=True):
        deal_id = row[0]       # A
        client_name = row[1]   # B
        birthdate_raw = row[3] # D

        if not deal_id or not birthdate_raw:
            continue

        if isinstance(birthdate_raw, datetime):
            birthdate = birthdate_raw
        else:
            birthdate = datetime.strptime(str(birthdate_raw), "%d.%m.%Y")

        results.append({
            "deal_id": int(deal_id),
            "client_name": client_name,
            "birthdate": birthdate
        })

    return results


def get_week_range():
    """
    Возвращает диапазон дат текущей недели (Пн–Вс)
    """
    today = datetime.now().date()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


class Command(BaseCommand):
    help = "Создаёт задачи в Битрикс24 на поздравления с ДР"

    def handle(self, *args, **kwargs):
        self.stdout.write("📘 Загружаю Excel...")
        deals = read_deals_from_excel(EXCEL_FILENAME)

        monday, sunday = get_week_range()
        self.stdout.write(f"📅 Неделя: {monday} — {sunday}")

        current_year = datetime.now().year
        tasks_created = 0

        for item in deals:
            deal_id = item["deal_id"]
            client_name = item["client_name"]
            birthdate = item["birthdate"]

            birthday_this_year = birthdate.replace(year=current_year).date()

            if monday <= birthday_this_year <= sunday:
                self.stdout.write(f"🎉 ДР {client_name}: {birthday_this_year}")

                result = create_task_for_birthday(
                    deal_id,
                    client_name,
                    birthday_this_year
                )

                tasks_created += 1

        self.stdout.write(
            self.style.SUCCESS(f"Готово! Создано задач: {tasks_created}")
        )
