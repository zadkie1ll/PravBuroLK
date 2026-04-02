from datetime import timedelta

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone


class CallSessionStatus(models.TextChoices):
    DRAFT = "draft", "Черновик"
    ACTIVE = "active", "Активна"
    COMPLETED = "completed", "Завершена"
    CANCELLED = "cancelled", "Отменена"


class CallEntityType(models.TextChoices):
    DEAL = "deal", "Сделки"
    LEAD = "lead", "Лиды"


class CallQueueItemStatus(models.TextChoices):
    NEW = "new", "Новый"
    IN_PROGRESS = "in_progress", "В работе"
    DONE = "done", "Завершен"
    POSTPONED = "postponed", "Перезвонить позже"
    SKIPPED = "skipped", "Пропущен"
    FAILED = "failed", "Недозвон"


class CallResult(models.TextChoices):
    NO_ANSWER = "no_answer", "Не ответил"
    BUSY = "busy", "Занято"
    UNAVAILABLE = "unavailable", "Недоступен"
    SUCCESS = "success", "Успешно"
    POSTPONED = "postponed", "Перезвонить позже"
    SKIPPED = "skipped", "Пропустить"


class CallSession(models.Model):
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="call_sessions",
    )
    entity_type = models.CharField(
        max_length=16,
        choices=CallEntityType.choices,
        default=CallEntityType.DEAL,
    )
    date_from = models.DateField()
    date_to = models.DateField()
    status = models.CharField(
        max_length=16,
        choices=CallSessionStatus.choices,
        default=CallSessionStatus.DRAFT,
    )
    filters_json = models.JSONField(default=dict, blank=True)
    total_items = models.PositiveIntegerField(default=0)
    processed_items = models.PositiveIntegerField(default=0)
    success_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at", "-id")

    def __str__(self):
        return f"Сессия #{self.pk} ({self.date_from} - {self.date_to})"

    def get_absolute_url(self):
        return reverse("call_queue:production_handler")


class CallQueueItem(models.Model):
    session = models.ForeignKey(
        CallSession,
        on_delete=models.CASCADE,
        related_name="items",
    )
    entity_type = models.CharField(
        max_length=16,
        choices=CallEntityType.choices,
        default=CallEntityType.DEAL,
    )
    bitrix_entity_id = models.BigIntegerField()
    bitrix_contact_id = models.BigIntegerField(null=True, blank=True)
    client_name = models.CharField(max_length=255, blank=True, default="")
    phone = models.CharField(max_length=64, blank=True, default="")
    lead_created_at = models.DateTimeField(null=True, blank=True)
    source_id = models.CharField(max_length=64, blank=True, default="")
    source_name = models.CharField(max_length=255, blank=True, default="")
    stage_id = models.CharField(max_length=64, blank=True, default="")
    stage_name = models.CharField(max_length=255, blank=True, default="")
    responsible_id = models.CharField(max_length=64, blank=True, default="")
    responsible_name = models.CharField(max_length=255, blank=True, default="")
    status = models.CharField(
        max_length=16,
        choices=CallQueueItemStatus.choices,
        default=CallQueueItemStatus.NEW,
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_call_queue_items",
    )
    locked_at = models.DateTimeField(null=True, blank=True)
    attempts_count = models.PositiveIntegerField(default=0)
    last_call_result = models.CharField(max_length=32, blank=True, default="")
    last_call_at = models.DateTimeField(null=True, blank=True)
    last_provider_call_id = models.CharField(max_length=128, blank=True, default="")
    bitrix_url = models.URLField(blank=True, default="")
    needs_manual_processing = models.BooleanField(default=False)
    repeat_unanswered = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("id",)
        constraints = [
            models.UniqueConstraint(
                fields=("session", "entity_type", "bitrix_entity_id"),
                name="call_queue_unique_session_entity",
            ),
        ]
        indexes = [
            models.Index(fields=("session", "status")),
            models.Index(fields=("session", "assigned_to")),
            models.Index(fields=("status", "locked_at")),
        ]

    def __str__(self):
        return f"{self.entity_type}:{self.bitrix_entity_id} / сессия {self.session_id}"

    @property
    def is_locked_stale(self) -> bool:
        if not self.locked_at:
            return False
        stale_after = timezone.now() - timedelta(minutes=30)
        return self.locked_at <= stale_after


class CallAttempt(models.Model):
    queue_item = models.ForeignKey(
        CallQueueItem,
        on_delete=models.CASCADE,
        related_name="attempts",
    )
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="call_attempts",
    )
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(default=timezone.now)
    result = models.CharField(max_length=32, choices=CallResult.choices)
    comment = models.TextField(blank=True, default="")
    provider_call_id = models.CharField(max_length=128, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(fields=("queue_item", "created_at")),
            models.Index(fields=("manager", "created_at")),
        ]

    def __str__(self):
        return f"Попытка #{self.pk} для {self.queue_item_id}"


class BitrixSyncLog(models.Model):
    entity_type = models.CharField(max_length=64)
    entity_id = models.CharField(max_length=128)
    action = models.CharField(max_length=64)
    request_payload = models.JSONField(default=dict, blank=True)
    response_payload = models.JSONField(default=dict, blank=True)
    success = models.BooleanField(default=False)
    error_text = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(fields=("entity_type", "entity_id")),
            models.Index(fields=("action", "created_at")),
            models.Index(fields=("success", "created_at")),
        ]

    def __str__(self):
        return f"{self.entity_type}:{self.entity_id} / {self.action}"
