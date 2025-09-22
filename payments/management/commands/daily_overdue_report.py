from datetime import date
from django.core.management.base import BaseCommand
from clients.models import Client
from payments.models import InstallmentPlan

class Command(BaseCommand):
    help = "Генерирует ежедневный отчёт по просроченным платежам"

    def handle(self, *args, **options):
        today = date.today()
        report = {}

        # Получаем все планы рассрочек с просроченными платежами
        overdue_plans = InstallmentPlan.objects.filter(
            payments__due_date__lt=today,
            payments__status__in=['pending', 'partial']
        ).distinct()

        if not overdue_plans.exists():
            self.stdout.write("Нет просроченных платежей на сегодня")
            return

        for plan in overdue_plans:
            client = plan.contract.client
            lines = []
            for payment in plan.payments.order_by('number'):
                line = (
                    f"{payment.number} | "
                    f"{payment.due_date.strftime('%d.%m.%Y')} | "
                    f"{payment.amount_paid}/{payment.amount_due} ₽ | "
                    f"{payment.get_status_display()}"
                )
                lines.append(line)
            report[client.id] = "\n".join(lines)

        # Выводим отчёт в консоль (можно заменить на отправку в телеграм/Bitrix)
        for client_id, summary in report.items():
            client = Client.objects.get(id=client_id)
            self.stdout.write(f"Клиент: {client}\n{summary}\n{'-'*50}")

        self.stdout.write("Ежедневный отчёт по просроченным платежам сгенерирован")