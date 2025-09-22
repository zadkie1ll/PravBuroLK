import requests
from django.contrib.auth.models import User
from django.db import transaction
from .models import Employee   # поправьте импорт под ваш путь

BITRIX_WEBHOOK = "https://prav-buro.bitrix24.ru/rest/24/pa1x5irnfpbcnh27/"

def fetch_bitrix_employees():
    """
    Получает всех сотрудников из Bitrix24
    """
    url = f"{BITRIX_WEBHOOK}user.get"
    params = {"ACTIVE": "true"}
    response = requests.get(url, params=params) 
    response.raise_for_status()
    return response.json().get("result", [])


@transaction.atomic
def sync_employees():
    """
    Создаёт/обновляет записи Employee:
    - для каждого bitrix_id создаёт Django User (логин btrx_{bitrix_id}, пароль btrx{bitrix_id})
    - обновляет/создаёт Employee с привязкой к этому User
    """
    bitrix_users = fetch_bitrix_employees()

    for b_user in bitrix_users:
        bitrix_id = b_user["ID"]

        # Формируем отображаемое имя
        parts = [b_user.get("LAST_NAME", ""), b_user.get("NAME", ""), b_user.get("SECOND_NAME", "")]
        full_name = " ".join(p for p in parts if p).strip() or b_user.get("NAME") or "Без имени"

        username = f"btrx_{bitrix_id}"
        raw_password = f"btrx{bitrix_id}"

        # --- 1. Создаём/обновляем Django User ---
        user, created = User.objects.get_or_create(
            username=username,
            defaults={"first_name": full_name}
        )
        if created:
            user.set_password(raw_password)
            user.save()
        else:
            # Обновляем имя, если оно изменилось
            if user.first_name != full_name:
                user.first_name = full_name
                user.save(update_fields=["first_name"])

        # --- 2. Создаём/обновляем Employee ---
        Employee.objects.update_or_create(
            bitrix_id=bitrix_id,
            defaults={
                "name": full_name,
                # если хотите хранить ссылку на User – добавьте поле user в модель Employee
                # "user": user
            }
        )
