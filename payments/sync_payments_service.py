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

        # --- Получаем первый контракт, если есть ---
        self.contract = client.contract_set.first()
        if self.contract:
            print(f"[BitrixSync] Найден контракт #{self.contract.id}")
        else:
            print(f"[BitrixSync] Контракт не найден")

        self.plan = getattr(self.contract, "installmentplan", None) if self.contract else None
        if self.plan:
            print(f"[BitrixSync] Найден план рассрочки #{self.plan.id}")
        else:
            print(f"[BitrixSync] План рассрочки не найден")

   # === Таблица платежей ===
    def build_payments_table(self):
        print(f"[BitrixSync] Формируем таблицу платежей")
        if not self.plan:
            print(f"[BitrixSync] Плана нет, возвращаем сообщение")
            return "Нет данных по рассрочке"

        col_widths = [4, 12, 15, 15, 15]  # ширина колонок

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
        print(f"[BitrixSync] Таблица платежей сформирована:\n{table_str}")
        return table_str

    # === Основные подсчёты ===
    def get_total_sum(self):
        total = Decimal("0.00")
        if self.contract:
            total = self.contract.total_amount - self.contract.discount
        print(f"[BitrixSync] Общая сумма договора: {total}")
        return total

    def is_deposit_paid(self):
        result = (
            self.client.other_payments.filter(payment_type__in=["deposit", "deposit_extra"], is_paid=True).exists()
            or getattr(self.contract, "deposit", False)
        )
        print(f"[BitrixSync] Депозит оплачен: {result}")
        return result

    def is_publication_paid(self):
        result = (
            self.client.other_payments.filter(payment_type__in=["publication", "publication_extra"], is_paid=True).exists()
            or getattr(self.contract, "publication", False)
        )
        print(f"[BitrixSync] Публикация оплачена: {result}")
        return result

    def is_extra_costs_paid(self):
        result = getattr(self.contract, "extra_court_costs", False)
        print(f"[BitrixSync] Доп. расходы оплачены: {result}")
        return result

    def get_next_payment_date(self):
        if not self.plan:
            return None
        next_payment = self.plan.payments.filter(status__in=["pending", "partial"]).order_by("due_date").first()
        result = next_payment.due_date if next_payment else None
        print(f"[BitrixSync] Следующий платёж: {result}")
        return result

    def has_overdue_payments(self):
        if not self.plan:
            print(f"[BitrixSync] План рассрочки отсутствует, просрочек нет")
            return False

        today = timezone.now().date()
        result = self.plan.payments.filter(due_date__lt=today).exclude(status='paid').exists()
        print(f"[BitrixSync] Есть просрочки (по дате и сумме): {result}")
        return result   

    # === Формирование данных для Bitrix ===
    def build_payload(self):
        print(f"[BitrixSync] Формируем payload для Bitrix")
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
            },
        }
        print(f"[BitrixSync] Payload готов:\n{payload}")
        return payload

    # === Отправка в Bitrix ===
    def send_to_bitrix(self):
        print(f"[BitrixSync] Отправка данных в Bitrix")
        payload = self.build_payload()
        url = f"{self.webhook_url}/crm.deal.update.json"
        response = requests.post(url, json=payload)
        print(f"[BitrixSync] Ответ Bitrix: {response.status_code} {response.text}")

        data = response.json()
        if not data.get("result"):
            raise ValueError(f"Ошибка Bitrix при обновлении клиента {self.client.id}: {data}")

        print(f"[BitrixSync] Данные успешно отправлены в Bitrix")
        return True


# === Утилита-обёртка ===
def sync_client_to_bitrix(client):
    print(f"[BitrixSync] Начало синхронизации клиента {client.id}")
    service = BitrixSyncService(client)
    result = service.send_to_bitrix()
    print(f"[BitrixSync] Синхронизация завершена для клиента {client.id}")
    return result