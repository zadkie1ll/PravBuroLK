from decimal import Decimal
from django.db import models, transaction
from django.utils import timezone
from .sync_payments_service import sync_client_to_bitrix

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
    order_id = models.CharField(max_length=100, blank=True, null=True)

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
        return extra

    def __str__(self):
        return f"Платеж #{self.number} — {self.get_status_display()} — {self.amount_due}₽"


class ActualPayment(models.Model):
    plan = models.ForeignKey(
        "InstallmentPlan",
        on_delete=models.CASCADE,
        related_name="actual_payments",
        blank=True,
        null=True
    )
    payment_date = models.DateField(null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    order_id = models.CharField(max_length=100, blank=True, null=True)

    # флаг, чтобы не применять платёж дважды
    is_applied = models.BooleanField(default=False, editable=False)

    def save(self, *args, **kwargs):
        """
        Сохраняем. При создании (is_new) запускаем apply_payment один раз.
        Флаг is_applied защищает от повторного применения.
        """
        is_new = self.pk is None
        super().save(*args, **kwargs)

        if is_new and not self.is_applied:
            try:
                # apply_payment установит is_applied через update, чтобы не вызывать рекурсивный save
                self.apply_payment()
            except Exception as e:
                # логируем, но не ломаем сохранение
                print(f"[ActualPayment] Ошибка при применении платежа: {e}")

    def apply_payment(self):
        """
        Распределяет фактический платёж по платежам плана строго по порядку (number),
        распределение продолжается пока есть remaining, создаются PaymentApplication записи.
        После успешного применения помечает self.is_applied = True (через queryset.update).
        Все изменения в транзакции.
        """
        if not self.plan:
            print("[ActualPayment] Нет плана — пропуск распределения")
            return

        # защитимся от повторного запуска
        if self.is_applied:
            print("[ActualPayment] Уже применён — выходим")
            return

        remaining = Decimal(self.amount or 0)
        if remaining <= 0:
            # пометим как применён, чтобы не пытаться снова
            ActualPayment.objects.filter(pk=self.pk).update(is_applied=True)
            print("[ActualPayment] Нулевая сумма — пометили как применённый")
            return

        # Начнём транзакцию — все изменения должны быть атомарны
        with transaction.atomic():
            payments_qs = self.plan.payments.select_for_update().order_by("number")
            # Перебираем по порядку и распределяем
            for inst_payment in payments_qs:
                if remaining <= Decimal("0.00"):
                    break

                to_pay = (inst_payment.amount_due or Decimal("0.00")) - (inst_payment.amount_paid or Decimal("0.00"))
                # если этот платёж уже оплачен — пропускаем
                if to_pay <= Decimal("0.00"):
                    continue

                applied = min(remaining, to_pay)

                # Создаём связь ActualPayment -> InstallmentPayment
                PaymentApplication.objects.create(
                    payment=inst_payment,
                    actual_payment=self,
                    applied_amount=applied,
                )

                # Обновляем платёж рассрочки
                inst_payment.amount_paid = (inst_payment.amount_paid or Decimal("0.00")) + applied
                if inst_payment.amount_paid >= inst_payment.amount_due:
                    inst_payment.status = "paid"
                    inst_payment.amount_paid = inst_payment.amount_due
                else:
                    inst_payment.status = "partial"
                inst_payment.save()

                remaining -= applied

            # Пометим ActualPayment как применённый (через queryset, чтобы не вызвать save() и рекурсию)
            ActualPayment.objects.filter(pk=self.pk).update(is_applied=True)

        # Логирование остатка
        if remaining > Decimal("0.00"):
            print(f"[ActualPayment] Остаток {remaining} ₽ не распределён (все платежи закрыты)")
        else:
            print(f"[ActualPayment] Платёж {self.amount} ₽ полностью распределён")
        
        # После успешного распределения — синхронизируем клиента (вне транзакции)
        try:
            if self.plan and getattr(self.plan, 'contract', None) and getattr(self.plan.contract, 'client', None):
                client = self.plan.contract.client
                sync_client_to_bitrix(client)
                print(f"[ActualPayment] Синхронизация клиента {client.id} завершена")
        except Exception as e:
            # не откатываем транзакцию из-за ошибок синхронизации
            print(f"[ActualPayment] Ошибка при синхронизации: {e}")


class PaymentApplication(models.Model):
    """Связь между фактическим платёжом и платежом по рассрочке"""
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

    def __str__(self):
        return f"{self.get_payment_type_display()} - {self.amount} ₽ для {self.client}"

    class Meta:
        verbose_name = "Прочий платеж"
        verbose_name_plural = "Прочие платежи"
        ordering = ['-created_at']