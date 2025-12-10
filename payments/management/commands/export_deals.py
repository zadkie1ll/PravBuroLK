from django.core.management.base import BaseCommand

from documents.utilitites.util import (
    fetch_enum_map,
    fetch_all_deals,
    export_to_excel,
    upload_excel_to_google_sheets,
    REGION_FIELD_NAME,
    CATEGORY_ID,
    EXCEL_FILENAME,
)


class Command(BaseCommand):
    help = "Экспорт сделок из Bitrix + загрузка в Google Sheets"

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Получаем карту регионов..."))
        region_map = fetch_enum_map(REGION_FIELD_NAME)

        self.stdout.write(self.style.NOTICE("Загружаем сделки..."))
        deals = fetch_all_deals(CATEGORY_ID)
        self.stdout.write(self.style.SUCCESS(f"Найдено {len(deals)} сделок."))

        self.stdout.write(self.style.NOTICE("Создаём Excel..."))
        export_to_excel(deals, region_map, EXCEL_FILENAME)

        self.stdout.write(self.style.NOTICE("Загружаем в Google Sheets..."))

        upload_excel_to_google_sheets(
            excel_filename=EXCEL_FILENAME,
            spreadsheet_id="15wntS-n3Gw72T_EXRctRDO8l6mlprRiFl8_XcBAR_c8",
            sheet_name="Дни рождения",
            credentials_file="burnished-block-442415-n4-0f8d850242ed.json",
        )

        self.stdout.write(self.style.SUCCESS("Готово!"))
