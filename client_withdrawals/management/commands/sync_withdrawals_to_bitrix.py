import logging
import time

from django.core.management.base import BaseCommand

from clients.models import Client
from client_withdrawals.services import (
    build_withdrawals_bitrix_fields,
    get_withdrawals_page_url,
    sync_withdrawals_to_bitrix,
)


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Массово обновляет в Bitrix поля страницы списаний клиента: "
        "ссылку на страницу и сводную таблицу."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--client-id",
            type=int,
            default=None,
            help="Обработать только одного клиента по внутреннему ID.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Ограничить количество клиентов для обработки.",
        )
        parser.add_argument(
            "--delay",
            type=float,
            default=0.2,
            help="Пауза между запросами в Bitrix в секундах.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Только показать, что будет отправлено, без обновления Bitrix.",
        )

    def handle(self, *args, **options):
        client_id = options["client_id"]
        limit = options["limit"]
        delay = options["delay"]
        dry_run = options["dry_run"]

        base_queryset = Client.objects.all().order_by("id")
        skipped_without_bitrix = base_queryset.filter(bitrix_id__isnull=True) | base_queryset.filter(bitrix_id__exact="")
        queryset = base_queryset.exclude(bitrix_id__isnull=True).exclude(bitrix_id__exact="")

        if client_id is not None:
            skipped_without_bitrix = skipped_without_bitrix.filter(id=client_id)
            queryset = queryset.filter(id=client_id)
        if limit:
            queryset = queryset[:limit]

        total = queryset.count()
        self.stdout.write(f"Найдено клиентов для синхронизации списаний: {total}")
        skipped_count = skipped_without_bitrix.count()
        if skipped_count:
            self.stdout.write(
                self.style.WARNING(
                    f"Пропущено клиентов без bitrix_id: {skipped_count}"
                )
            )

        success = 0
        failed = 0

        for index, client in enumerate(queryset, start=1):
            page_url = get_withdrawals_page_url(client)
            fields = build_withdrawals_bitrix_fields(client)

            if dry_run:
                self.stdout.write(
                    f"[DRY] [{index}/{total}] client_id={client.id}, "
                    f"bitrix_id={client.bitrix_id}, url={page_url}"
                )
                for field_code, value in fields.items():
                    preview = value if len(str(value)) <= 160 else f"{str(value)[:157]}..."
                    self.stdout.write(f"      {field_code}: {preview}")
                continue

            try:
                sync_withdrawals_to_bitrix(client)
                success += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✅ [{index}/{total}] Клиент {client.id} синхронизирован: {page_url}"
                    )
                )
            except Exception as exc:
                failed += 1
                message = (
                    f"❌ [{index}/{total}] Ошибка синхронизации клиента "
                    f"{client.id} (bitrix_id={client.bitrix_id}): {exc}"
                )
                self.stderr.write(message)
                logger.exception(message)

            if delay:
                time.sleep(delay)

        if dry_run:
            self.stdout.write(f"[DRY] Завершено. Просмотрено клиентов: {total}.")
            return

        self.stdout.write(
            f"Готово. Успешно: {success}, Ошибок: {failed}, Всего: {total}."
        )
