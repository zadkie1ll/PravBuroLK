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