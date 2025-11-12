import os
import logging
import requests
from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import models, IntegrityError
from clients.models import Client
from payments.sync_payments_service import sync_client_to_bitrix 

BITRIX_API_URL = "https://prav-buro.bitrix24.ru/rest/24/pa1x5irnfpbcnh27/crm.deal.list.json"


class Command(BaseCommand):
    help = "Присваивает клиентам bitrix_id по сделкам из канбана C2, сверяя ФИО (гибкий поиск) и синхронизирует их с Bitrix"

    def handle(self, *args, **options):
        log_dir = os.path.join(settings.BASE_DIR, "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, "bitrix_id_assign.log")

        logging.basicConfig(
            filename=log_path,
            level=logging.INFO,
            format="%(asctime)s — %(levelname)s — %(message)s",
            encoding="utf-8"
        )

        self.stdout.write(f"📝 Лог сохраняется в: {log_path}")
        logging.info("=== Начало обработки клиентов ===")

        clients = Client.objects.filter(models.Q(bitrix_id__isnull=True) | models.Q(bitrix_id=""))
        total = clients.count()
        self.stdout.write(f"🔎 Найдено {total} клиентов без bitrix_id")
        logging.info(f"Найдено {total} клиентов без bitrix_id")

        deals = self.get_all_deals_from_bitrix()
        self.stdout.write(f"📋 Загружено {len(deals)} сделок из Битрикс")
        logging.info(f"Загружено {len(deals)} сделок из Битрикс")

        updated = 0
        for client in clients.iterator(chunk_size=100):
            full_name = f"{client.surname} {client.name or ''} {client.middlename or ''}".strip()
            if not full_name:
                logging.warning(f"⛔ Пропущен клиент ID={client.id}: нет ФИО")
                continue

            matched = self.find_matching_deal(full_name, deals)

            if matched:
                deal_id, deal_title = matched

                existing = Client.objects.filter(bitrix_id=str(deal_id)).exclude(id=client.id).first()
                if existing:
                    msg = (
                        f"⚠ Дубликат bitrix_id {deal_id}: "
                        f"клиенты {client.id} ({full_name}) и {existing.id} "
                        f"({existing.surname} {existing.name or ''} {existing.middlename or ''})"
                    )
                    self.stdout.write(self.style.WARNING(msg))
                    logging.warning(msg)
                    continue  

                try:
                    client.bitrix_id = str(deal_id)
                    client.save(update_fields=["bitrix_id"])

                    # ✅ Сразу после обновления — синхронизируем с Bitrix
                    try:
                        sync_client_to_bitrix(client)
                        msg = f"✅ {full_name} → {deal_title} (ID {deal_id}) — синхронизировано с Bitrix"
                        self.stdout.write(self.style.SUCCESS(msg))
                        logging.info(msg)
                    except Exception as sync_error:
                        msg = f"⚠ Ошибка синхронизации для {full_name} (ID {deal_id}): {sync_error}"
                        self.stdout.write(self.style.WARNING(msg))
                        logging.warning(msg)

                    updated += 1

                except IntegrityError as e:
                    msg = f"❌ Ошибка при сохранении клиента {client.id} ({full_name}): {e}"
                    self.stdout.write(self.style.ERROR(msg))
                    logging.error(msg)

            else:
                msg = f"⚠ Не найдено совпадений для {full_name}"
                self.stdout.write(self.style.WARNING(msg))
                logging.warning(msg)

        logging.info(f"=== Обработка завершена: обновлено {updated} клиентов ===")
        self.stdout.write(self.style.SUCCESS(f"🚀 Все клиенты обработаны (обновлено {updated})"))

    def get_all_deals_from_bitrix(self):
        """Возвращает список сделок (id, title) из категории C2."""
        all_deals = []
        start = 0

        try:
            while True:
                response = requests.get(
                    BITRIX_API_URL,
                    params={
                        "filter[CATEGORY_ID]": 2,
                        "select[]": ["ID", "TITLE"],
                        "start": start
                    },
                    timeout=15
                )
                response.raise_for_status()
                data = response.json()

                result = data.get("result", [])
                all_deals.extend([(int(d["ID"]), d["TITLE"]) for d in result])

                if "next" not in data:
                    break
                start = data["next"]

            return all_deals

        except Exception as e:
            logging.error(f"Ошибка при запросе сделок из Битрикс: {e}")
            self.stdout.write(self.style.ERROR(f"❌ Ошибка при запросе сделок из Битрикс: {e}"))
            return []

    def find_matching_deal(self, full_name, deals):
        """Поиск сделки с постепенным уточнением: фамилия → имя → отчество."""
        parts = full_name.split()
        if not parts:
            return None

        last_name = parts[0]
        name = parts[1] if len(parts) > 1 else ""
        mid_name = parts[2] if len(parts) > 2 else ""

        matches = [(id_, title) for id_, title in deals if last_name.lower() in title.lower()]
        if len(matches) == 1:
            return matches[0]
        if not matches:
            return None

        if name:
            matches = [(id_, title) for id_, title in matches if name.lower() in title.lower()]
            if len(matches) == 1:
                return matches[0]

        if mid_name:
            matches = [(id_, title) for id_, title in matches if mid_name.lower() in title.lower()]
            if len(matches) == 1:
                return matches[0]

        if len(matches) > 1:
            titles = "; ".join([t for _, t in matches])
            logging.warning(f"❗ Неоднозначное совпадение для {full_name}: {titles}")
        return None
