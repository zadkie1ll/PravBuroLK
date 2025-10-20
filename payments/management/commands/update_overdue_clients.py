from django.core.management.base import BaseCommand
from django.utils import timezone
from clients.models import Client
from payments.models import InstallmentPayment
from payments.sync_payments_service import sync_client_to_bitrix


class Command(BaseCommand):
    help = "Обновляет статусы просроченных платежей и синхронизирует клиентов с Битрикс24"

    def handle(self, *args, **options):
        today = timezone.now().date()

        # --- 1️⃣ Обновляем статусы платежей ---
        self.stdout.write("🔄 Обновляем статусы платежей...")
        updated = InstallmentPayment.objects.filter(
            due_date__lt=today               # срок уже прошёл
        ).exclude(
            status='paid'                    # исключаем уже оплаченные
        ).update(status='overdue')           # массовое обновление

        self.stdout.write(f"✅ Обновлено {updated} платежей в статус 'overdue'")

        # --- 2️⃣ Ищем клиентов с просроченными платежами ---
        overdue_client_ids = InstallmentPayment.objects.filter(
            status='overdue'
        ).values_list(
            'plan__contract__client_id', flat=True
        ).distinct()

        clients_with_overdue = Client.objects.filter(id__in=overdue_client_ids)
        total_clients = clients_with_overdue.count()
        self.stdout.write(f"📊 Найдено {total_clients} клиентов с просроченными платежами")

        if not total_clients:
            self.stdout.write("🎉 Просроченных клиентов нет — вы молодцы!")
            return

        # --- 3️⃣ Обновляем статусы клиентов и синхронизируем ---
        for client in clients_with_overdue.iterator(chunk_size=100):
            try:
                # ⚙️ Укажи правильное поле, если статус хранится иначе
                if hasattr(client, "status"):
                    client.status = "overdue"
                    client.save(update_fields=["status"])

                # Синхронизируем с Битрикс
                sync_client_to_bitrix(client)

                self.stdout.write(self.style.SUCCESS(f"✅ Клиент {client} обновлён и синхронизирован"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"❌ Ошибка при обработке клиента {client}: {e}"))

        self.stdout.write(self.style.SUCCESS("🚀 Обработка завершена успешно"))
