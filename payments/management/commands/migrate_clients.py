import json
import logging
from django.utils.dateparse import parse_date
from django.utils import timezone
from decimal import Decimal
import requests
from payments.models import ActualPayment, OtherPayment
from django.core.management.base import BaseCommand
from clients.services import ClientService  # Твой инкапсулированный сервис

# Если позже будет сервис для платежей — импортируешь его аналогично


class Command(BaseCommand):
    help = "Мигрирует клиентов и их платежи из старого приложения в новое"

    def add_arguments(self, parser):
        parser.add_argument(
            "--source-url",
            type=str,
            required=True,
            help="Базовый URL старого приложения, например: http://oldapp.local/api"
        )
        parser.add_argument(
            "--start-id",
            type=int,
            default=0,
            help="Начать миграцию с определённого клиента (для возобновления)"
        )

    def handle(self, *args, **options):
        base_url = options["source_url"].rstrip("/")
        start_id = options["start_id"]

        # Настраиваем логирование
        logging.basicConfig(
            filename="migrate_clients.log",
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s",
        )
        console = logging.StreamHandler()
        console.setLevel(logging.INFO)
        console.setFormatter(logging.Formatter("%(asctime)s | %(message)s", "%H:%M:%S"))
        logging.getLogger().addHandler(console)

        logging.info("=== Запуск миграции клиентов ===")

        try:
            ids_resp = requests.get(f"{base_url}/api/clients/ids/")
            ids_resp.raise_for_status()
            ids_data = ids_resp.json()
            client_ids = ids_data.get("clients", [])
        except Exception as e:
            logging.error(f"Не удалось получить список клиентов: {e}")
            return

        logging.info(f"Найдено клиентов: {len(client_ids)}")

        for idx, client_id in enumerate(client_ids, start=1):
            if client_id < start_id:
                continue  # Позволяет перезапускать с середины
            logging.info(f"[{idx}/{len(client_ids)}] Миграция клиента ID={client_id}")

            try:
                # Получаем данные клиента
                client_resp = requests.get(f"{base_url}/clients/{client_id}/")
                client_resp.raise_for_status()
                client_data = client_resp.json()

                # Получаем платежи
                payments_resp = requests.get(f"{base_url}/api/client/{client_id}/payments/")
                payments_resp.raise_for_status()
                payments_data = payments_resp.json()

                # Создаём клиента через твой сервис
                # Здесь ты сам добавишь соответствие полей
                client, contract, plan = ClientService.create_client_with_contract(
                    username=client_data.get("username"),
                    password="temp_password",
                    name=client_data.get("name", ""),
                    surname=client_data.get("lastname", ""),
                    middlename=client_data.get("middlename", ""),
                    email=client_data.get("email", "client@prav-buro.ru"),
                    bitrix_id=str(client_data.get("id")),
                    stage="1",
                    total_amount=client_data.get("sumall"),
                    discount=0,
                    first_payment = client_data.get("sumoplachen"),
                    first_payment_date=client_data.get("datestartwork"),
                    number_of_payments=10,
                    preferred_payment_day=15,
                )

                logging.info(f"✅ Клиент создан: {client.id}")

                # Создание платежей (заготовка, если нужно — ты вставишь реальную логику)
                self.create_client_payments(client, payments_data)
                logging.info(f"💰 Платежи клиента {client.id} обработаны")

            except requests.HTTPError as e:
                logging.error(f"Ошибка HTTP при обработке клиента {client_id}: {e}")
            except Exception as e:
                logging.exception(f"❌ Ошибка при миграции клиента {client_id}: {e}")

        logging.info("=== Миграция завершена ===")

    def create_client_payments(self, client, payments_data: dict):
        """
        Создаёт платежи клиента:
        - ClientOplata → ActualPayment (по плану рассрочки)
        - ClientOplataSud / ClientOplataOther → OtherPayment
        """
        oplata = payments_data.get("ClientOplata", []) or []
        oplata_sud = payments_data.get("ClientOplataSud", []) or []
        oplata_other = payments_data.get("ClientOplataOther", []) or []

        total = len(oplata) + len(oplata_sud) + len(oplata_other)
        if total == 0:
            logging.info(f"У клиента {client.id} нет платежей")
            return

        logging.info(
            f"→ Обрабатываем {total} платежей клиента {client.id} "
            f"(Oplata={len(oplata)}, Sud={len(oplata_sud)}, Other={len(oplata_other)})"
        )

        # === ClientOplata → рассрочка ===
        if oplata:
            plan = getattr(client, "contract", None)
            if plan and hasattr(plan, "installmentplan"):
                plan = plan.installmentplan
            else:
                logging.warning(f"⚠ У клиента {client.id} нет рассрочки, пропускаем ClientOplata")
                plan = None

            for record in oplata:
                if not record or not isinstance(record, dict):
                    continue

                raw_sum = record.get("sum") or record.get("amount") or record.get("summa")
                if not raw_sum:
                    continue

                try:
                    amount = Decimal(str(raw_sum).replace(",", "."))
                except Exception:
                    continue

                if amount <= 0:
                    continue

                payment_date = parse_date(str(record.get("date")))
                try:
                    ActualPayment.objects.create(
                        plan=plan,
                        amount=amount,
                        payment_date=payment_date
                    )
                    logging.debug(f"💸 ActualPayment создан: {amount} ₽ ({payment_date})")
                except Exception as e:
                    logging.error(f"Ошибка при создании ActualPayment клиента {client.id}: {e}")

        # === Все прочие платежи → OtherPayment ===
        # Объединим обе категории, чтобы не дублировать код
        all_other = []
        for record in oplata_sud:
            record["_source"] = "sud"
            all_other.append(record)
        for record in oplata_other:
            record["_source"] = "other"
            all_other.append(record)

        for record in all_other:
            if not record or not isinstance(record, dict):
                continue

            raw_sum = record.get("sum") or record.get("amount") or record.get("summa")
            if not raw_sum:
                logging.debug(f"⚠ Пропуск прочего платежа без суммы: {record}")
                continue

            try:
                amount = Decimal(str(raw_sum).replace(",", "."))
            except Exception:
                logging.debug(f"⚠ Некорректная сумма в прочем платеже: {record}")
                continue

            if amount <= 0:
                logging.debug(f"⚠ Пропуск нулевого прочего платежа: {record}")
                continue

            comment = record.get("comment", "") or ""
            source = record.get("_source")

            # Определяем тип платежа
            if source == "sud":
                # Судебные платежи
                payment_type = "deposit"
                if "публикац" in comment.lower():
                    payment_type = "publication"
            else:
                # Прочие платежи
                payment_type = "post"
                if "депозит" in comment.lower():
                    payment_type = "deposit_extra"
                elif "публикац" in comment.lower():
                    payment_type = "publication_extra"

            try:
                OtherPayment.objects.create(
                    client=client,
                    payment_type=payment_type,
                    amount=amount,
                    is_paid=True,
                    paid_at=timezone.now(),
                    comment=comment or f"Платёж ({source})"
                )
                logging.info(
                    f"📄 OtherPayment создан: {amount} ₽ ({payment_type}) — {comment or 'без комментария'}"
                )
            except Exception as e:
                logging.error(f"Ошибка при создании прочего платежа клиента {client.id}: {e}")

        logging.info(f"💰 Все платежи клиента {client.id} успешно обработаны")