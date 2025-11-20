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
        base_url = getattr(settings, "SITE_BASE_URL", "https://prav-buro.ru")
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
                "partial": "⚠ Частично",
            }.get(p.status, "Ожидается")

            line = " | ".join([
                fmt(p.number, col_widths[0], "right"),
                fmt(p.due_date.strftime("%d.%m.%Y"), col_widths[1]),
                fmt(f"{p.amount_due:,.2f} ₽", col_widths[2], "right"),
                fmt(f"{p.amount_paid:,.2f} ₽", col_widths[3], "right"),
                fmt(status_display, col_widths[4]),
            ])
            lines.append(line)

        return "\n".join(lines)

    def get_total_sum(self):
        if not self.contract:
            return Decimal("0.00")
        return self.contract.total_amount - self.contract.discount

    def is_deposit_paid(self):
        return (
            self.client.other_payments.filter(
                payment_type__in=["deposit", "deposit_extra"], is_paid=True
            ).exists()
            or getattr(self.contract, "deposit", False)
        )

    def is_publication_paid(self):
        return (
            self.client.other_payments.filter(
                payment_type__in=["publication", "publication_extra"], is_paid=True
            ).exists()
            or getattr(self.contract, "publication", False)
        )

    def is_extra_costs_paid(self):
        return getattr(self.contract, "extra_court_costs", False)

    def get_next_payment_date(self):
        if not self.plan:
            return None
        
        next_payment = self.plan.payments.filter(
            status__in=["pending", "partial"]
        ).order_by("due_date").first()

        return next_payment.due_date if next_payment else None

    def has_overdue_payments(self):
        if not self.plan:
            return False

        today = timezone.now().date()

        return self.plan.payments.filter(
            due_date__lt=today
        ).exclude(status='paid').exists()

    def build_payload(self):
        if not self.bitrix_id:
            raise ValueError(f"У клиента {self.client} нет Bitrix ID")

        next_payment = self.get_next_payment_date()

        payload = {
            "id": self.bitrix_id,
            "fields": {
                "UF_CRM_1760618096": self.build_payments_table(),
                "OPPORTUNITY": str(self.get_total_sum()),  # ВАЖНО: Bitrix не любит float
                "UF_CRM_1760618033886": 1 if self.is_deposit_paid() else 0,
                "UF_CRM_1760618045973": 1 if self.is_publication_paid() else 0,
                "UF_CRM_1760618075429": 1 if self.is_extra_costs_paid() else 0,
                "UF_CRM_1760618180": next_payment.strftime("%Y-%m-%d") if next_payment else None,
                "UF_CRM_IS_DEBTOR": 1 if self.has_overdue_payments() else 0,
                "UF_CRM_1762350803092": self.get_admin_url(),
            },
        }

        return payload

    def send_to_bitrix(self):
        payload = self.build_payload()

        url = f"{self.webhook_url}/crm.deal.update.json"

        data = {"id": payload["id"]}

        for key, value in payload["fields"].items():
            if value is not None:  
                data[f"fields[{key}]"] = value

        print("\n[BitrixSync → Bitrix] Payload:")
        print(data)

        response = requests.post(url, data=data)

        print("[BitrixSync ← Bitrix] Response:")
        print(response.text)

        try:
            result = response.json()
        except:
            raise ValueError(f"Bitrix вернул некорректный JSON: {response.text}")

        if not result.get("result"):
            raise ValueError(
                f"Ошибка Bitrix при обновлении сделки ID={self.client.id}: {result}"
            )

        return True


def sync_client_to_bitrix(client):
    service = BitrixSyncService(client)
    return service.send_to_bitrix()
