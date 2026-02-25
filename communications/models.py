from django.db import models


class CallWebhookEvent(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        DONE = "done", "Done"
        FAILED = "failed", "Failed"
        IGNORED = "ignored", "Ignored"

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    event_name = models.CharField(max_length=128, blank=True)
    call_id = models.CharField(max_length=128, blank=True)
    lead_id = models.CharField(max_length=128, blank=True)
    deal_id = models.CharField(max_length=128, blank=True)
    contact_id = models.CharField(max_length=128, blank=True)
    record_file_id = models.CharField(max_length=128, blank=True)
    dedupe_key = models.CharField(max_length=255, blank=True, db_index=True)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    attempts = models.PositiveIntegerField(default=0)
    raw_payload = models.JSONField(default=dict, blank=True)
    audio_file_path = models.CharField(max_length=512, blank=True)
    transcript = models.JSONField(default=list, blank=True)
    analysis = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)

    def __str__(self) -> str:
        return f"CallWebhookEvent(id={self.id}, status={self.status}, call_id={self.call_id})"


class CallProcessingLog(models.Model):
    class Level(models.TextChoices):
        INFO = "info", "Info"
        WARNING = "warning", "Warning"
        ERROR = "error", "Error"

    created_at = models.DateTimeField(auto_now_add=True)
    event = models.ForeignKey(
        CallWebhookEvent,
        on_delete=models.CASCADE,
        related_name="logs",
    )
    level = models.CharField(max_length=16, choices=Level.choices, default=Level.INFO)
    message = models.CharField(max_length=512)
    details = models.JSONField(default=dict, blank=True)

    def __str__(self) -> str:
        return f"CallProcessingLog(event_id={self.event_id}, level={self.level})"


class ProcessedCallArchive(models.Model):
    """
    Архив "чистых" кейсов: только полностью обработанные звонки.
    Эта таблица хранится в отдельной БД (см. ARCHIVE_DB в settings.py).
    """

    created_at = models.DateTimeField(auto_now_add=True)
    source_event_id = models.PositiveIntegerField(db_index=True)
    call_id = models.CharField(max_length=128, blank=True)
    lead_id = models.CharField(max_length=128, blank=True)
    deal_id = models.CharField(max_length=128, blank=True)
    contact_id = models.CharField(max_length=128, blank=True)
    record_file_id = models.CharField(max_length=128, blank=True)
    audio_file_path = models.CharField(max_length=512, blank=True)
    transcript = models.JSONField(default=list, blank=True)
    analysis = models.JSONField(default=dict, blank=True)
    source_payload = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["created_at"]),
            models.Index(fields=["call_id"]),
            models.Index(fields=["lead_id"]),
            models.Index(fields=["deal_id"]),
            models.Index(fields=["contact_id"]),
        ]

    def __str__(self) -> str:
        return f"ProcessedCallArchive(source_event_id={self.source_event_id}, call_id={self.call_id})"
