import requests
import time
from django.core.management.base import BaseCommand
from clients.models import Client


BITRIX_WEBHOOK = "https://prav-buro.bitrix24.ru/rest/24/pa1x5irnfpbcnh27"


class Command(BaseCommand):
    help = "Синхронизирует acquiring_enabled с Bitrix по полю UF_CRM_1760099004"

    # Настройки
    REQUEST_TIMEOUT = 5                # таймаут запроса
    SLEEP_BETWEEN_REQUESTS = 0.3       # пауза между запросами (сек)
    RETRY_LIMIT = 3                    # кол-во повторных попыток

    def handle(self, *args, **options):
        clients = Client.objects.exclude(bitrix_id__isnull=True).exclude(bitrix_id="")

        total = clients.count()
        updated = 0
        errors = 0

        self.stdout.write(f"Начинаю проверку {total} клиентов...\n")

        for client in clients:
            bitrix_id = client.bitrix_id

            deal = self.fetch_deal(bitrix_id)

            if not deal:
                self.stdout.write(self.style.ERROR(f"[{client.id}] Не удалось получить сделку"))
                errors += 1
                continue

            # --- Проверяем поле ---
            field_value = str(deal.get("UF_CRM_1760099004") or "")
            acquiring_flag = (field_value == "2022")

            # --- Обновляем только если есть изменение ---
            if client.acquiring_enabled != acquiring_flag:
                client.acquiring_enabled = acquiring_flag
                client.save(update_fields=["acquiring_enabled"])
                updated += 1
                self.stdout.write(self.style.SUCCESS(
                    f"[{client.id}] acquiring_enabled → {acquiring_flag}"
                ))
            else:
                self.stdout.write(
                    f"[{client.id}] без изменений (уже {client.acquiring_enabled})"
                )

            # --- Пауза между запросами ---
            time.sleep(self.SLEEP_BETWEEN_REQUESTS)

        self.stdout.write("\n--- Готово ---")
        self.stdout.write(f"Обработано: {total}")
        self.stdout.write(f"Обновлено acquiring_enabled: {updated}")
        self.stdout.write(f"Ошибок: {errors}")

    # --- Функция безопасного получения данных сделки ---
    def fetch_deal(self, bitrix_id):
        """Делает GET запрос к Bitrix с retry и защитой от rate-limit"""

        url = f"{BITRIX_WEBHOOK}/crm.deal.get.json?ID={bitrix_id}"

        for attempt in range(1, self.RETRY_LIMIT + 1):
            try:
                response = requests.get(url, timeout=self.REQUEST_TIMEOUT)
                data = response.json()

                # Слишком много запросов / временная ошибка
                if any(x in str(data).lower() for x in ["too_many", "rate", "limit"]):
                    self.stdout.write(self.style.WARNING(
                        f"Bitrix rate-limit, попытка {attempt}/{self.RETRY_LIMIT}"
                    ))
                    time.sleep(1.5 * attempt)
                    continue

                # Нет результата
                if "result" not in data:
                    return None

                return data["result"]

            except requests.exceptions.Timeout:
                self.stdout.write(self.style.WARNING(
                    f"Timeout при запросе сделки {bitrix_id}, попытка {attempt}"
                ))
                time.sleep(1.5 * attempt)

            except Exception as e:
                self.stdout.write(self.style.ERROR(
                    f"Ошибка запроса Bitrix (попытка {attempt}): {e}"
                ))
                time.sleep(1.5 * attempt)

        return None
