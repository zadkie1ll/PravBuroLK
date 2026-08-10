import re

import requests
from django.conf import settings
from django.core.management.base import BaseCommand

from lead_control.bitrix_api import (
    BitrixAPIError,
    build_deal_copy_fields,
    create_deal,
    list_deals,
)


def normalize_name(title):
    if not title:
        return ""
    t = title.lower()
    t = re.sub(r"\(.*?\)", "", t)
    t = re.sub(r"[^\w\s]", "", t, flags=re.UNICODE)
    t = re.sub(r"\s+", " ", t).strip()
    return t


class Command(BaseCommand):
    help = (
        "Разовый бэкфилл: копирует все завершённые (WON) сделки категории "
        "'Сопровождение' в категорию 'Агенты' на первую стадию, пропуская "
        "контакты (и совпадающие ФИО), у которых сделка в 'Агенты' уже есть."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Только показать, что будет скопировано, без обращений crm.deal.add",
        )
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Не спрашивать подтверждение перед реальным копированием",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Скопировать только первые N сделок из списка (для пробного запуска)",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        skip_confirm = options["yes"]
        limit = options["limit"]

        source_category_id = settings.DEAL_DUPLICATION_SOURCE_CATEGORY_ID
        source_won_stage_id = settings.DEAL_DUPLICATION_SOURCE_WON_STAGE_ID
        target_category_id = settings.DEAL_DUPLICATION_TARGET_CATEGORY_ID
        target_first_stage_id = settings.DEAL_DUPLICATION_TARGET_FIRST_STAGE_ID

        self.stdout.write(self.style.NOTICE("Загружаем WON-сделки из 'Сопровождения'..."))
        source_deals = list_deals(source_category_id, stage_id=source_won_stage_id)
        self.stdout.write(self.style.SUCCESS(f"Найдено {len(source_deals)} сделок в 'Сопровождении'."))

        self.stdout.write(self.style.NOTICE("Загружаем существующие сделки 'Агенты' (для защиты от дублей)..."))
        target_deals = list_deals(target_category_id, select=["ID", "CONTACT_ID", "TITLE"])
        existing_contact_ids = {
            str(deal["CONTACT_ID"])
            for deal in target_deals
            if deal.get("CONTACT_ID")
        }
        existing_names = {
            normalize_name(deal.get("TITLE"))
            for deal in target_deals
            if normalize_name(deal.get("TITLE"))
        }
        self.stdout.write(self.style.SUCCESS(
            f"В 'Агенты' уже есть сделки для {len(existing_contact_ids)} контактов "
            f"({len(existing_names)} уникальных ФИО)."
        ))

        to_copy = []
        skipped_no_contact = 0
        skipped_duplicate_contact = 0
        skipped_duplicate_name = 0
        seen_contact_ids = set(existing_contact_ids)
        seen_names = set(existing_names)

        for deal in source_deals:
            contact_id = deal.get("CONTACT_ID")
            if not contact_id:
                skipped_no_contact += 1
                continue
            contact_id = str(contact_id)
            name = normalize_name(deal.get("TITLE"))

            if contact_id in seen_contact_ids:
                skipped_duplicate_contact += 1
                continue
            if name and name in seen_names:
                skipped_duplicate_name += 1
                continue

            seen_contact_ids.add(contact_id)
            if name:
                seen_names.add(name)
            to_copy.append(deal)

        self.stdout.write("")
        self.stdout.write(self.style.NOTICE("Итог:"))
        self.stdout.write(f"  К копированию: {len(to_copy)}")
        self.stdout.write(f"  Пропущено (уже есть в 'Агенты' по CONTACT_ID): {skipped_duplicate_contact}")
        self.stdout.write(f"  Пропущено (уже есть в 'Агенты' по совпадению ФИО): {skipped_duplicate_name}")
        self.stdout.write(f"  Пропущено (нет CONTACT_ID): {skipped_no_contact}")
        self.stdout.write("")

        for deal in to_copy:
            self.stdout.write(
                f"  ID={deal.get('ID')}  CONTACT_ID={deal.get('CONTACT_ID')}  "
                f"TITLE={deal.get('TITLE')!r}"
            )

        if not to_copy:
            self.stdout.write(self.style.SUCCESS("Копировать нечего."))
            return

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry-run: реальных изменений в Bitrix не было."))
            return

        if limit is not None:
            to_copy = to_copy[:limit]
            self.stdout.write(self.style.WARNING(f"--limit {limit}: будут скопированы только первые {len(to_copy)}."))

        if not skip_confirm:
            answer = input(
                f"\nСоздать {len(to_copy)} новых сделок в 'Агенты'? [y/N]: "
            ).strip().lower()
            if answer not in ("y", "yes", "да"):
                self.stdout.write(self.style.WARNING("Отменено пользователем."))
                return

        created = 0
        errors = 0
        for deal in to_copy:
            fields = build_deal_copy_fields(deal, target_category_id, target_first_stage_id)
            try:
                new_deal_id = create_deal(fields)
            except (BitrixAPIError, requests.exceptions.RequestException) as exc:
                errors += 1
                self.stdout.write(self.style.ERROR(
                    f"  Ошибка копирования сделки ID={deal.get('ID')}: {exc}"
                ))
                continue
            created += 1
            self.stdout.write(self.style.SUCCESS(
                f"  Сделка ID={deal.get('ID')} -> новая сделка ID={new_deal_id}"
            ))

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Готово. Создано: {created}. Ошибок: {errors}."))
