from django.core.management.base import BaseCommand
from clients.models import Client
from payments.sync_payments_service import sync_client_to_bitrix
import logging
import time

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Синхронизирует всех клиентов с Bitrix через sync_client_to_bitrix."

    def add_arguments(self, parser):
        parser.add_argument(
            "--only-with-bitrix-id",
            action="store_true",
            help="Синхронизировать только клиентов, у которых заполнен bitrix_id.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Ограничить количество клиентов для синхронизации.",
        )
        parser.add_argument(
            "--delay",
            type=float,
            default=0.0,
            help="Добавить паузу между запросами (в секундах), чтобы не перегружать Bitrix.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Показать клиентов без фактической отправки в Bitrix.",
        )

    def handle(self, *args, **options):
        only_with_bitrix_id = options["only_with_bitrix_id"]
        limit = options["limit"]
        delay = options["delay"]
        dry_run = options["dry_run"]

        qs = Client.objects.all()
        if only_with_bitrix_id:
            qs = qs.exclude(bitrix_id__isnull=True).exclude(bitrix_id__exact="")

        if limit:
            qs = qs[:limit]

        total = qs.count()
        self.stdout.write(f"🔄 Найдено клиентов для синхронизации: {total}")

        success = 0
        failed = 0

        for idx, client in enumerate(qs, start=1):
            if dry_run:
                self.stdout.write(f"[DRY] Клиент {client.id}: {client}")
                continue

            try:
                sync_client_to_bitrix(client)
                success += 1
                self.stdout.write(f"✅ [{idx}/{total}] Клиент {client.id} ({client}) синхронизирован.")
            except Exception as e:
                failed += 1
                msg = f"❌ [{idx}/{total}] Ошибка при синхронизации клиента {client.id}: {e}"
                self.stderr.write(msg)
                logger.exception(msg)

            if delay:
                time.sleep(delay)

        if not dry_run:
            self.stdout.write(f"\nГотово. Успешно: {success}, Ошибок: {failed}.")
        else:
            self.stdout.write(f"\n[DRY] Завершено. Клиентов просмотрено: {total}.")
