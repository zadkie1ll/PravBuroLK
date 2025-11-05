import requests
from decimal import Decimal
from django.conf import settings
from django.utils import timezone


class BitrixSyncService:
    def __init__(self, client):
        print(f"[BitrixSync] Инициализация для клиента {client.id}")
        self.client = client
        self.bitrix_id = client.bitrix_id
        self.webhook_url = "https://prav-buro.bitrix24.ru/rest/24/pa1x5irnfpbcnh27"

        self.contract = client.contract_set.first()

        self.plan = getattr(self.contract, "installmentplan", None) if self.contract else None

    def get_admin_url(self):
        """Формирует URL на страницу администрирования клиента"""
        base_url = getattr(settings, "SITE_BASE_URL", "http://127.0.0.1:8000")
        return f"{base_url}/client_admin/{self.client.id}/"

    def build_payments_table(self):
        if not self.plan:
            return "Нет данных по рассрочке"

        col_widths = [4, 12, 15, 15, 15] 

        def fmt(text, width, align="left"):
            text = str(text)
            return text.rjust(width) if align == "right" else text.ljust(width)

        lines = []

        for p in self.plan.payments.order_by("number"):
            status_display = {
                "paid": "✅ Оплачен",
                "overdue": "❌ Просрочен",
                "partial": "⚠ Частично"
            }.get(p.status, "Ожидается")

            line = " | ".join([
                fmt(p.number, col_widths[0], "right"),
                fmt(p.due_date.strftime("%d.%m.%Y"), col_widths[1]),
                fmt(f"{p.amount_due:,.2f} ₽", col_widths[2], "right"),
                fmt(f"{p.amount_paid:,.2f} ₽", col_widths[3], "right"),
                fmt(status_display, col_widths[4]),
            ])
            lines.append(line)

        table_str = "\n".join(lines)
        return table_str

    def get_total_sum(self):
        total = Decimal("0.00")
        if self.contract:
            total = self.contract.total_amount - self.contract.discount
        return total

    def is_deposit_paid(self):
        result = (
            self.client.other_payments.filter(payment_type__in=["deposit", "deposit_extra"], is_paid=True).exists()
            or getattr(self.contract, "deposit", False)
        )
        return result

    def is_publication_paid(self):
        result = (
            self.client.other_payments.filter(payment_type__in=["publication", "publication_extra"], is_paid=True).exists()
            or getattr(self.contract, "publication", False)
        )
        return result

    def is_extra_costs_paid(self):
        result = getattr(self.contract, "extra_court_costs", False)
        return result

    def get_next_payment_date(self):
        if not self.plan:
            return None
        next_payment = self.plan.payments.filter(status__in=["pending", "partial"]).order_by("due_date").first()
        result = next_payment.due_date if next_payment else None
        return result

    def has_overdue_payments(self):
        if not self.plan:
            return False

        today = timezone.now().date()
        result = self.plan.payments.filter(due_date__lt=today).exclude(status='paid').exists()
        return result   

    def build_payload(self):
        if not self.bitrix_id:
            raise ValueError(f"У клиента {self.client} нет Bitrix ID")

        payload = {
            "id": self.bitrix_id,
            "fields": {
                "UF_CRM_1760618096": str(self.build_payments_table()),
                "OPPORTUNITY": float(self.get_total_sum()),
                "UF_CRM_1760618033886": 1 if self.is_deposit_paid() else 0,
                "UF_CRM_1760618045973": 1 if self.is_publication_paid() else 0,
                "UF_CRM_1760618075429": 1 if self.is_extra_costs_paid() else 0,
                "UF_CRM_1760618180": self.get_next_payment_date().strftime("%Y-%m-%d")
                if self.get_next_payment_date() else None,
                "UF_CRM_IS_DEBTOR": 1 if self.has_overdue_payments() else 0,
                "UF_CRM_1762350803092": self.get_admin_url(),
            },
        }
        return payload

    def send_to_bitrix(self):
        payload = self.build_payload()
        url = f"{self.webhook_url}/crm.deal.update.json"
        response = requests.post(url, json=payload)

        data = response.json()
        if not data.get("result"):
            raise ValueError(f"Ошибка Bitrix при обновлении клиента {self.client.id}: {data}")

        return True


def sync_client_to_bitrix(client):
    service = BitrixSyncService(client)
    result = service.send_to_bitrix()
    return result
