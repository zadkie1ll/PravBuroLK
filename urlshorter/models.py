import re

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

class UrlShortener(models.Model):
    source = models.CharField(max_length=100, unique=True, help_text="Уникальный идентификатор (например, 'tgchat')")
    destination = models.URLField(help_text="Целевая ссылка (например, 'https://t.me/chat')")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.source} -> {self.destination}"

class Click(models.Model):
    url = models.ForeignKey(UrlShortener, on_delete=models.CASCADE, related_name='clicks')
    social = models.CharField(max_length=50, blank=True, null=True, help_text="Источник клика (например, 'tiktok')")
    ip_address = models.GenericIPAddressField(blank=True, null=True)  # Опционально: IP пользователя
    user_agent = models.TextField(blank=True, null=True)  # Опционально: Браузер/устройство
    clicked_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Click on {self.url.source} from {self.social} at {self.clicked_at}"


# --- Новая система разметки (ТЗ: доработка сервиса разметки ссылок) ---
# Ниже — отдельные таблицы, не связанные с UrlShortener/Click выше.
# Старые данные и старая логика редиректа этот код не трогают.

UTM_FREE_TEXT_RE = re.compile(r'^[a-z0-9-]+$')


def validate_utm_free_text(value):
    if not UTM_FREE_TEXT_RE.match(value):
        raise ValidationError(
            "Разрешены только латинские буквы, цифры и дефис (без подчёркивания и пробелов)."
        )


class UtmSource(models.Model):
    """Справочник utm_source. Значения не удаляются — скрываются (is_active=False)."""
    code = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.code


class UtmMedium(models.Model):
    """Справочник utm_medium (cpc / organic)."""
    code = models.CharField(max_length=50, unique=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.code


class BotBlock(models.Model):
    """Справочник ключей блока бота (consultation, chat, pristavi и т.д.)."""
    key = models.CharField(max_length=50, unique=True)
    title = models.CharField(max_length=200)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.key} — {self.title}"


class MarketingLink(models.Model):
    LINK_TYPE_SITE = "site"
    LINK_TYPE_BOT = "bot"
    LINK_TYPE_OTHER = "other"
    LINK_TYPE_CHOICES = [
        (LINK_TYPE_SITE, "Сайт (классическая UTM)"),
        (LINK_TYPE_BOT, "Telegram-бот"),
        (LINK_TYPE_OTHER, "Прочие площадки"),
    ]

    source = models.SlugField(max_length=150, unique=True, help_text="Короткий код в адресе редиректа")
    link_type = models.CharField(max_length=10, choices=LINK_TYPE_CHOICES)
    destination = models.URLField(help_text="Целевая ссылка (для типа 'бот' — адрес бота)")

    utm_source = models.ForeignKey(UtmSource, on_delete=models.PROTECT, related_name="links")
    utm_medium = models.ForeignKey(UtmMedium, on_delete=models.PROTECT, related_name="links")
    utm_campaign = models.CharField(max_length=100, validators=[validate_utm_free_text])
    utm_content = models.CharField(max_length=100, blank=True, validators=[validate_utm_free_text])
    utm_term = models.CharField(max_length=100, blank=True, validators=[validate_utm_free_text])

    bot_block = models.ForeignKey(
        BotBlock, on_delete=models.PROTECT, related_name="links", null=True, blank=True,
        help_text="Только для link_type=bot",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "link_type", "destination", "utm_source", "utm_medium",
                    "utm_campaign", "utm_content", "utm_term", "bot_block",
                ],
                name="unique_marketing_link_combo",
            )
        ]

    def save(self, *args, **kwargs):
        self.utm_campaign = self.utm_campaign.lower()
        self.utm_content = self.utm_content.lower()
        self.utm_term = self.utm_term.lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.source} ({self.get_link_type_display()})"


BOT_PREVIEW_USER_AGENTS = (
    "TelegramBot",
    "vkShare",
    "facebookexternalhit",
    "Twitterbot",
    "WhatsApp",
    "SkypeUriPreview",
)


class MarketingClick(models.Model):
    link = models.ForeignKey(MarketingLink, on_delete=models.CASCADE, related_name="clicks")
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True, null=True)
    is_bot_preview = models.BooleanField(default=False)
    clicked_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Click on {self.link.source} at {self.clicked_at}"