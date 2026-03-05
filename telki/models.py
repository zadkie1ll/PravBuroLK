import uuid

from django.db import models


class March8Greeting(models.Model):
    client = models.ForeignKey(
        "clients.Client",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="march8_greetings",
        verbose_name="Клиентка",
    )
    recipient_name = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Имя девушки",
        help_text="Можно оставить пустым, если выбрана клиентка.",
    )
    birth_date = models.DateField(verbose_name="Дата рождения")
    personal_text = models.TextField(verbose_name="Персональный текст поздравления")

    custom_background = models.ImageField(
        upload_to="telki/backgrounds/",
        blank=True,
        null=True,
        verbose_name="Кастомный фон",
    )
    astrology_image = models.ImageField(
        upload_to="telki/astrology/",
        blank=True,
        null=True,
        verbose_name="Астрологическая картинка",
    )
    certificate_url = models.URLField(
        blank=True,
        null=True,
        verbose_name="Ссылка на сертификат",
    )

    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    is_active = models.BooleanField(default=True, verbose_name="Активно")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Поздравление на 8 марта"
        verbose_name_plural = "Поздравления на 8 марта"
        ordering = ("recipient_name",)

    def __str__(self):
        return self.recipient_name

    def save(self, *args, **kwargs):
        if self.client and not self.recipient_name:
            self.recipient_name = str(self.client).strip()
        super().save(*args, **kwargs)
