from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models


class ClientWithdrawalRecord(models.Model):
    client = models.ForeignKey(
        "clients.Client",
        on_delete=models.CASCADE,
        related_name="withdrawal_records",
        verbose_name="Клиент",
    )
    withdrawal_date = models.DateField(verbose_name="Дата снятия")
    transfer_date = models.DateField(blank=True, null=True, verbose_name="Дата перевода")
    withdrawal_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Сумма снятия",
    )
    transferred_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name="Сумма перевода",
    )
    tail_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name='Остаток "хвоста"',
    )
    comment = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Комментарий",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-withdrawal_date", "-id"]
        verbose_name = "Запись по списанию клиента"
        verbose_name_plural = "Записи по списаниям клиентов"

    def __str__(self):
        return f"{self.client} | {self.withdrawal_date} | {self.withdrawal_amount}"

    def clean(self):
        super().clean()
        if self.withdrawal_amount is not None and self.withdrawal_amount < 0:
            raise ValidationError({"withdrawal_amount": "Сумма снятия не может быть отрицательной."})
        if self.transferred_amount is not None and self.transferred_amount < 0:
            raise ValidationError({"transferred_amount": "Сумма перевода не может быть отрицательной."})
        if (
            self.withdrawal_amount is not None
            and self.transferred_amount is not None
            and self.transferred_amount > self.withdrawal_amount
        ):
            raise ValidationError({"transferred_amount": "Сумма перевода не может быть больше суммы снятия."})

    def save(self, *args, **kwargs):
        self.full_clean()
        if self.transferred_amount is None:
            self.tail_amount = self.withdrawal_amount or Decimal("0.00")
        else:
            self.tail_amount = (self.withdrawal_amount or Decimal("0.00")) - self.transferred_amount
        super().save(*args, **kwargs)
