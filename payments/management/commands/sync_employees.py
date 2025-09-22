from django.core.management.base import BaseCommand
from clients.bitrix_employees_sync import sync_employees

class Command(BaseCommand):
    help = "Синхронизирует сотрудников из Bitrix24 в модель Employee и создает пользователей"

    def handle(self, *args, **options):
        sync_employees()
        self.stdout.write(self.style.SUCCESS("Сотрудники успешно синхронизированы"))