from decimal import Decimal
from django.db import models, transaction
from django.utils import timezone
from simple_history.models import HistoricalRecords  # ✅ добавлено
from .sync_payments_service import sync_client_to_bitrix
from django.db import IntegrityError


class Contract(models.Model):
    client = models.ForeignKey('clients.Client', on_delete=models.CASCADE)

    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    first_payment = models.DecimalField(max_digits=10, decimal_places=2)
    first_payment_date = models.DateField()
    number_of_payments = models.PositiveIntegerField()
    preferred_payment_day = models.PositiveIntegerField(default=15)

    # --- Служебные поля ---
    created_at = models.DateTimeField(auto_now_add=True)

    # --- Показательные флаги ---
    deposit = models.BooleanField(default=False, help_text="Оплачен судебный депозит")
    publication = models.BooleanField(default=False, help_text="Оплачена публикация")
    extra_court_costs = models.BooleanField(default=False, help_text="Оплачены доп. судебные расходы")

    # ✅ История изменений
    history = HistoricalRecords()

    def __str__(self):
        return f"Contract #{self.id} — {self.client}"


class InstallmentPlan(models.Model):
    contract = models.OneToOneField(Contract, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    calculated = models.BooleanField(default=False)

    # ✅ История изменений
    history = HistoricalRecords()

    def __str__(self):
        return f"InstallmentPlan for Contract #{self.contract.id}"


class InstallmentPayment(models.Model):
    plan = models.ForeignKey(InstallmentPlan, on_delete=models.CASCADE, related_name='payments')
    number = models.PositiveIntegerField()
    due_date = models.DateField()
    amount_due = models.DecimalField(max_digits=10, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(max_length=10, default='pending')

    order_id = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    bank_order_id = models.CharField(max_length=100, blank=True, null=True, db_index=True)

    history = HistoricalRecords()

    def apply_payment(self, amount):
        # Упростить до нуля
        return

    def __str__(self):
        return f"Платеж #{self.number} — {self.amount_due}₽"    


class ActualPayment(models.Model):
    plan = models.ForeignKey(
        "InstallmentPlan",
        on_delete=models.CASCADE,
        related_name="actual_payments",
        blank=True,
        null=True
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True, db_index=True)
    payment_date = models.DateField(null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    order_id = models.CharField(max_length=100, blank=True, null=True)

    # Реально больше не нужен, но пусть останется
    is_applied = models.BooleanField(default=False, editable=False)

    history = HistoricalRecords()

    def save(self, *args, **kwargs):
        # НЕТ автоприменения — самое главное
        super().save(*args, **kwargs)

    def apply_payment(self):
        # Полностью выключено
        return


class PaymentApplication(models.Model):
    payment = models.ForeignKey(
        'InstallmentPayment',
        on_delete=models.CASCADE,
        related_name='applications'
    )
    actual_payment = models.ForeignKey(
        'ActualPayment',
        on_delete=models.CASCADE,
        related_name='applications'
    )
    applied_amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        actual_date = getattr(self.actual_payment, 'payment_date', 'None')
        return f"{self.applied_amount} ₽ → {self.payment} ({actual_date})"

class OtherPayment(models.Model):
    PAYMENT_TYPES = [
        ('deposit', 'Судебный депозит'),
        ('publication', 'Публикация'),
        ('post', 'Почтовые расходы'),
        ('deposit_extra', 'Дополнительный депозит'),
        ('publication_extra', 'Дополнительная публикация'),
    ]

    client = models.ForeignKey('clients.Client', on_delete=models.CASCADE, related_name='other_payments')
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    is_paid = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(blank=True, null=True)
    comment = models.TextField(blank=True, null=True)

    # ✅ История изменений
    history = HistoricalRecords()

    def __str__(self):
        return f"{self.get_payment_type_display()} - {self.amount} ₽ для {self.client}"

    class Meta:
        verbose_name = "Прочий платеж"
        verbose_name_plural = "Прочие платежи"
        ordering = ['-created_at']
        
        
        
        
        
        
        
#SIMPLE OPLATAS ZAEBALO NAHUI UJE ETO PEREDELIVAT` YA OCHEN USTAL U MENYA MOZG KIPIT-------------------------------------------------------------------------------------------------------

