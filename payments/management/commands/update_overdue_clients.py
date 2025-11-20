import time
import requests
from django.core.management.base import BaseCommand
from django.utils import timezone
from clients.models import Client
from payments.models import InstallmentPayment
from payments.sync_payments_service import sync_client_to_bitrix


class Command(BaseCommand):
    help = "Обновляет статусы просроченных платежей и синхронизирует клиентов с Битрикс24"

    def handle(self, *args, **options):
        today = timezone.now().date()
        self.stdout.write("🔄 Обновляем статусы платежей...")

        to_overdue = InstallmentPayment.objects.filter(
            due_date__lt=today,
        ).exclude(
            status__in=['paid', 'overdue']
        )

        overdue_ids = list(to_overdue.values_list('id', flat=True))
        updated_count = to_overdue.update(status='overdue')

        self.stdout.write(f"✅ Обновлено {updated_count} платежей в статус 'overdue'")

        if not overdue_ids:
            self.stdout.write("🎉 Новых просроченных платежей нет")
            return

        overdue_client_ids = InstallmentPayment.objects.filter(
            id__in=overdue_ids
        ).values_list(
            'plan__contract__client_id', flat=True
        ).distinct()

        clients_with_new_overdue = Client.objects.filter(id__in=overdue_client_ids)
        total_clients = clients_with_new_overdue.count()

        self.stdout.write(f"📊 Найдено {total_clients} клиентов с новыми просрочками")

        for client in clients_with_new_overdue.iterator(chunk_size=100):
            try:
                self.stdout.write(f"[BitrixSync] Синхронизация клиента {client.id} ({client})")

                if hasattr(client, "status"):
                    client.status = "overdue"
                    client.save(update_fields=["status"])

                sync_client_to_bitrix(client)

                self.stdout.write(self.style.SUCCESS(f"✅ Клиент {client} обновлён и синхронизирован"))

            except requests.exceptions.RequestException as e:
                self.stdout.write(self.style.ERROR(f"⚠ Ошибка сети при обработке клиента {client}: {e}"))
                continue

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"❌ Ошибка при обработке клиента {client}: {e}"))
                continue

            time.sleep(0.5)

        self.stdout.write(self.style.SUCCESS("🚀 Обработка завершена успешно"))