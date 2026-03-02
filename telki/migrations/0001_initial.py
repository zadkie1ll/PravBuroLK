import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("clients", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="March8Greeting",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "recipient_name",
                    models.CharField(
                        blank=True,
                        help_text="Можно оставить пустым, если выбрана клиентка.",
                        max_length=255,
                        verbose_name="Имя девушки",
                    ),
                ),
                ("birth_date", models.DateField(verbose_name="Дата рождения")),
                ("personal_text", models.TextField(verbose_name="Персональный текст поздравления")),
                (
                    "custom_background",
                    models.ImageField(
                        blank=True,
                        null=True,
                        upload_to="telki/backgrounds/",
                        verbose_name="Кастомный фон",
                    ),
                ),
                (
                    "astrology_image",
                    models.ImageField(
                        blank=True,
                        null=True,
                        upload_to="telki/astrology/",
                        verbose_name="Астрологическая картинка",
                    ),
                ),
                (
                    "certificate_pdf",
                    models.FileField(
                        blank=True,
                        null=True,
                        upload_to="telki/certificates/",
                        verbose_name="PDF-сертификат",
                    ),
                ),
                ("token", models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True)),
                ("is_active", models.BooleanField(default=True, verbose_name="Активно")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "client",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="march8_greetings",
                        to="clients.client",
                        verbose_name="Клиентка",
                    ),
                ),
            ],
            options={
                "verbose_name": "Поздравление на 8 марта",
                "verbose_name_plural": "Поздравления на 8 марта",
                "ordering": ("recipient_name",),
            },
        ),
    ]
