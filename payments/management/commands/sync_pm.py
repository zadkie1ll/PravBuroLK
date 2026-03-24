import re
from decimal import Decimal
import requests
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand
from django.utils import timezone
from bitrix.models import Region, PmRate


class Command(BaseCommand):
    help = "Скачивает ПМ с сайта СФР и обновляет в базе"

    URL = "https://sfr.gov.ru/grazhdanam/dop_info/prozhitochniy_min_deti/"

    def handle(self, *args, **options):
        self.stdout.write("Загружаем страницу ПМ...")
        resp = requests.get(self.URL)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        tbody = soup.select_one(
            "body > main > section.re-container.re-container--grazhdanam > div > div.re-container__inner-main-container > div.re-container__inner-left > div > div > div > table > tbody"
        )
        if not tbody:
            self.stdout.write(self.style.ERROR("Не найден tbody таблицы на странице"))
            return

        rows = tbody.find_all("tr")
        self.stdout.write(f"Найдено строк таблицы: {len(rows)}")

        for tr in rows:
            cols = [td.get_text(strip=True) for td in tr.find_all("td")]
            if len(cols) < 6:
                continue

            # структура: [№, код, регион, общий ПМ, ПМ трудоспособных, ПМ детей, ...]
            region_name = cols[2]
            pm_all = self._parse_decimal(cols[3])
            pm_working = self._parse_decimal(cols[4])
            pm_child = self._parse_decimal(cols[5])

            # пробуем найти регион из базы (по вхождению)
            qs = Region.objects.filter(name__icontains=region_name)
            if not qs.exists():
                self.stdout.write(self.style.WARNING(f"Регион '{region_name}' не найден в базе"))
                continue

            for region in qs:
                today = timezone.now().date()
                pm_rate, created = PmRate.objects.update_or_create(
                    region=region,
                    effective_from=today,
                    defaults={
                        "pm_working": pm_working,
                        "pm_pensioner": pm_all,  # если отдельного ПМ пенсионера нет, можно взять общий
                        "pm_child": pm_child,
                    }
                )
                action = "Создан" if created else "Обновлён"
                self.stdout.write(f"{action} ПМ для {region.name}: {pm_working}/{pm_child}")

        self.stdout.write(self.style.SUCCESS("Парсинг и обновление ПМ завершены."))

    def _parse_decimal(self, value: str) -> Decimal:
        # преобразует строку вида '20 230,00' в Decimal('20230.00')
        clean = re.sub(r"[^\d,\.]", "", value).replace(",", ".").replace(" ", "")
        try:
            return Decimal(clean)
        except Exception:
            return Decimal("0")