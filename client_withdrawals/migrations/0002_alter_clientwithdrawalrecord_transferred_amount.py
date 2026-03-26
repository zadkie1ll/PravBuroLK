from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("client_withdrawals", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="clientwithdrawalrecord",
            name="transferred_amount",
            field=models.DecimalField(
                blank=True,
                null=True,
                max_digits=12,
                decimal_places=2,
                verbose_name="Сумма перевода",
            ),
        ),
    ]
