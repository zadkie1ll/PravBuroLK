import random
import string
import requests

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import transaction

from clients.models import Client

BITRIX_WEBHOOK = "https://prav-buro.bitrix24.ru/rest/24/pa1x5irnfpbcnh27/"


def generate_password(length=8):
    """Генерация простого пароля"""
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))


class Command(BaseCommand):
    help = "Генерация и обновление паролей клиентов, отправка данных в Bitrix24"

    def handle(self, *args, **options):
        clients = Client.objects.select_related('user').all()
        self.stdout.write(self.style.NOTICE(f"🔄 Найдено клиентов: {clients.count()}"))

        for client in clients:
            user = client.user
            if not user:
                self.stdout.write(self.style.WARNING(f"⚠️ У клиента {client.id} нет связанного пользователя"))
                continue

            new_password = generate_password()

            try:
                with transaction.atomic():
                    user.set_password(new_password)
                    user.save()

                    if client.bitrix_id:
                        deal_id = client.bitrix_id.strip()
                        bitrix_url = f"{BITRIX_WEBHOOK}crm.deal.update.json"

                        auth_text = f"{user.username}\n{new_password}"

                        payload = {
                            "id": deal_id,
                            "fields": {
                                "UF_CRM_1745888913952": auth_text 
                            }
                        }

                        response = requests.post(bitrix_url, json=payload)
                        data = response.json()

                        if data.get("error"):
                            self.stdout.write(self.style.ERROR(
                                f"❌ Ошибка Bitrix для клиента {user.username}: {data.get('error_description', data.get('error'))}"
                            ))
                        else:
                            self.stdout.write(self.style.SUCCESS(
                                f"✅ Клиент {user.username} обновлён, пароль: {new_password}"
                            ))
                    else:
                        self.stdout.write(self.style.WARNING(
                            f"⚠️ У клиента {user.username} нет bitrix_id — пропуск Bitrix"
                        ))

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"❗ Ошибка при обработке {user.username}: {e}"))

        self.stdout.write(self.style.SUCCESS("🎉 Все клиенты обработаны."))