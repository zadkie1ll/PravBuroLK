from django.db import models
from django.utils import timezone


class Contract(models.Model):
    client = models.ForeignKey('clients.Client', on_delete=models.CASCADE)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    first_payment = models.DecimalField(max_digits=10, decimal_places=2)
    first_payment_date = models.DateField()
    number_of_payments = models.PositiveIntegerField()
    preferred_payment_day = models.PositiveIntegerField(default=15)
    created_at = models.DateTimeField(auto_now_add=True)
    deposit = models.BooleanField(default=False)
    publication = models.BooleanField(default=False)

    
    
    def __str__(self):
        return f"Contract #{self.id} — {self.client}"


class InstallmentPlan(models.Model):
    contract = models.OneToOneField(Contract, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    calculated = models.BooleanField(default=False)

    def __str__(self):
        return f"InstallmentPlan for Contract #{self.contract.id}"


class InstallmentPayment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Ожидается'),
        ('paid', 'Оплачен'),
        ('partial', 'Частично оплачен'),
        ('overdue', 'Просрочен'),
    ]

    plan = models.ForeignKey(InstallmentPlan, on_delete=models.CASCADE, related_name='payments')
    number = models.PositiveIntegerField()
    due_date = models.DateField()
    amount_due = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')

    def __str__(self):
        return f"Платеж #{self.number} — {self.get_status_display()} — {self.amount_due}₽"


class ActualPayment(models.Model):
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE)
    date = models.DateField(default=timezone.now)
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"Платеж {self.amount}₽ от {self.date}"




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

    def __str__(self):
        return f"{self.get_payment_type_display()} - {self.amount} ₽ для {self.client}"

    class Meta:
        verbose_name = "Прочий платеж"
        verbose_name_plural = "Прочие платежи"
        ordering = ['-created_at']