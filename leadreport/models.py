# app/models.py
from django.db import models
from django.conf import settings
from django.utils import timezone


class SalesManager(models.Model):
    bitrix_user_id = models.BigIntegerField(unique=True, db_index=True)
    name = models.CharField(max_length=255)

    email = models.EmailField(blank=True, default="")
    phone = models.CharField(max_length=64, blank=True, default="")
    megafon_user = models.CharField(max_length=128, blank=True, default="")
    megafon_group = models.CharField(max_length=128, blank=True, default="")
    megafon_clid = models.CharField(max_length=64, blank=True, default="")

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_manager_profile",
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return self.name


class LeadSource(models.Model):
    """
    Справочник источников лидов.
    bitrix_id — ID источника в Bitrix24 (если используется интеграция).
    """
    name = models.CharField(max_length=255, unique=True)
    bitrix_id = models.BigIntegerField(null=True, blank=True, unique=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return self.name


class LeadEntry(models.Model):
    manager = models.ForeignKey(
        SalesManager,
        on_delete=models.PROTECT,
        related_name="lead_entries",
    )

    occurred_at = models.DateTimeField(default=timezone.now)

    source = models.ForeignKey(
        LeadSource,
        on_delete=models.PROTECT,
        related_name="leads",
    )

    comment = models.TextField(blank=True, default="")

    bitrix_lead_id = models.BigIntegerField(null=True, blank=True, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-occurred_at",)
        indexes = [
            models.Index(fields=["manager", "occurred_at"]),
            models.Index(fields=["occurred_at"]),
            models.Index(fields=["source"]),
        ]

    def __str__(self):
        return f"Lead #{self.id} / {self.occurred_at:%Y-%m-%d}"
    
    
    
class IssuedCredentialLog(models.Model):
    """
    Лог выдачи логина/пароля. Пароль хранится в открытом виде — доступ только админам.
    Рекомендация: периодически чистить (например, раз в 30 дней).
    """
    manager = models.ForeignKey(
        "SalesManager",
        on_delete=models.CASCADE,
        related_name="credential_logs",
    )
    username = models.CharField(max_length=150)
    password = models.CharField(max_length=128)

    issued_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-issued_at",)

    def __str__(self):
        return f"{self.username} @ {self.issued_at:%Y-%m-%d %H:%M}"
    
