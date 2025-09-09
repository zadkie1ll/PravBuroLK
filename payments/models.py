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
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')

    def apply_payment(self, amount):
        """Применяем платёж к этому месяцу"""
        self.amount_paid += amount
        if self.amount_paid >= self.amount_due:
            self.status = "paid"
            extra = self.amount_paid - self.amount_due
            self.amount_paid = self.amount_due
        elif self.amount_paid > 0:
            self.status = "partial"
            extra = 0
        else:
            self.status = "pending"
            extra = 0
        self.save()
        return extra  # если переплата → вернём остаток

    def __str__(self):
        return f"Платеж #{self.number} — {self.get_status_display()} — {self.amount_due}₽"


class ActualPayment(models.Model):
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE)
    date = models.DateField(default=timezone.now)
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)  # сначала сохраняем платёж

        # распределяем сумму по ближайшим платежам рассрочки
        plan = InstallmentPlan.objects.filter(contract=self.contract).first()
        if not plan:
            return

        remaining = self.amount
        for payment in plan.payments.filter(status__in=['pending', 'partial']).order_by('due_date'):
            if remaining <= 0:
                break

            before = payment.amount_paid
            remaining = payment.apply_payment(remaining)
            applied = payment.amount_paid - before

            if applied > 0:
                PaymentApplication.objects.create(
                    payment=payment,
                    actual_payment=self,
                    applied_amount=applied
                )

    def __str__(self):
        return f"Факт. платёж {self.amount}₽ от {self.date}"


class PaymentApplication(models.Model):
    """Связь между фактическим платёжом и платежом по рассрочке"""
    payment = models.ForeignKey(
        InstallmentPayment,
        on_delete=models.CASCADE,
        related_name='applications'
    )
    actual_payment = models.ForeignKey(
        ActualPayment,
        on_delete=models.CASCADE,
        related_name='applications'
    )
    applied_amount = models.DecimalField(max_digits=10, decimal_places=2)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.applied_amount} ₽ → {self.payment} ({self.actual_payment.date})"


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