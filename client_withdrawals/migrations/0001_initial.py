from decimal import Decimal

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("clients", "0002_client_isblocked_historicalclient_isblocked"),
    ]

    operations = [
        migrations.CreateModel(
            name="ClientWithdrawalRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("withdrawal_date", models.DateField(verbose_name="Дата снятия")),
                ("transfer_date", models.DateField(blank=True, null=True, verbose_name="Дата перевода")),
                ("withdrawal_amount", models.DecimalField(decimal_places=2, max_digits=12, verbose_name="Сумма снятия")),
                ("transferred_amount", models.DecimalField(decimal_places=2, max_digits=12, verbose_name="Сумма перевода")),
                ("tail_amount", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12, verbose_name='Остаток "хвоста"')),
                ("comment", models.CharField(blank=True, max_length=255, verbose_name="Комментарий")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "client",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="withdrawal_records",
                        to="clients.client",
                        verbose_name="Клиент",
                    ),
                ),
            ],
            options={
                "verbose_name": "Запись по списанию клиента",
                "verbose_name_plural": "Записи по списаниям клиентов",
                "ordering": ["-withdrawal_date", "-id"],
            },
        ),
    ]
