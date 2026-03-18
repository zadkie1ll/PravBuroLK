from django.contrib import admin
from django.utils.safestring import mark_safe
import json

from communications.models import CallProcessingLog, CallWebhookEvent, ProcessedCallArchive


# ─── Inline для логов (оставляем как было) ───
class CallProcessingLogInline(admin.TabularInline):
    model = CallProcessingLog
    extra = 0
    fields = ("created_at", "level", "message")
    readonly_fields = fields
    can_delete = False
    show_change_link = True
    ordering = ("-created_at",)


@admin.register(CallWebhookEvent)
class CallWebhookEventAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "event_name",
        "call_id",
        "lead_id",
        "deal_id",
        "contact_id",
        "record_file_id",
        "status",
        "attempts",
        "created_at",
    )
    list_filter = ("status", "event_name", "created_at")
    search_fields = ("call_id", "lead_id", "deal_id", "contact_id", "record_file_id", "error_message")
    readonly_fields = (
        "created_at",
        "updated_at",
        "pretty_raw_payload",
        "pretty_transcript",
        "pretty_analysis",
    )
    fields = (
        "created_at",
        "updated_at",
        "event_name",
        "call_id",
        "lead_id",
        "deal_id",
        "contact_id",
        "record_file_id",
        "dedupe_key",
        "status",
        "attempts",
        "error_message",
        "audio_file_path",
        "pretty_raw_payload",
        "pretty_transcript",
        "pretty_analysis",
    )
    inlines = [CallProcessingLogInline]
    ordering = ("-created_at",)

    def pretty_raw_payload(self, obj):
        return self._as_pretty_json(obj.raw_payload)

    def pretty_transcript(self, obj):
        return self._as_pretty_json(obj.transcript)

    def pretty_analysis(self, obj):
        return self._as_pretty_json(obj.analysis)

    @staticmethod
    def _as_pretty_json(value) -> str:
        if value is None:
            return mark_safe("<pre>{}</pre>")
        rendered = json.dumps(value, ensure_ascii=False, indent=2)
        return mark_safe(f"<pre style='white-space:pre-wrap; max-width:900px;'>{rendered}</pre>")


@admin.register(CallProcessingLog)
class CallProcessingLogAdmin(admin.ModelAdmin):
    list_display = ("id", "event", "level", "message", "created_at")
    list_filter = ("level", "created_at")
    search_fields = ("message", "event__call_id", "event__lead_id", "event__deal_id", "event__contact_id")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)


@admin.register(ProcessedCallArchive)
class ProcessedCallArchiveAdmin(admin.ModelAdmin):  # ← было ArchiveDBModelAdmin — подставь свой класс, если нужно
    list_display = (
        "id",
        "created_at",
        "source_event_id",
        "call_id",
        "lead_id",
        "deal_id",
        "contact_id",
        "record_file_id",
    )
    list_filter = (
        "created_at",
        "call_id",
        "lead_id",
        "deal_id",
    )
    search_fields = (
        "call_id",
        "lead_id",
        "deal_id",
        "contact_id",
        "record_file_id",
        "source_event_id",
    )
    readonly_fields = (
        "created_at",
        "source_event_id",
        "call_id",
        "lead_id",
        "deal_id",
        "contact_id",
        "record_file_id",
        "audio_file_path",
        "pretty_transcript",
        "pretty_analysis",
        "pretty_source_payload",
    )
    ordering = ("-created_at",)

    fields = (
        "created_at",
        "source_event_id",
        "call_id",
        "lead_id",
        "deal_id",
        "contact_id",
        "record_file_id",
        "audio_file_path",
        "pretty_transcript",
        "pretty_analysis",
        "pretty_source_payload",
    )

    # ─── Красивая отрисовка JSON-полей ───
    def pretty_transcript(self, obj):
        return self._as_pretty_json(obj.transcript)

    def pretty_analysis(self, obj):
        return self._as_pretty_json(obj.analysis)

    def pretty_source_payload(self, obj):
        return self._as_pretty_json(obj.source_payload)

    pretty_transcript.short_description = "Transcript"
    pretty_analysis.short_description = "Analysis"
    pretty_source_payload.short_description = "Source Payload"

    # Можно вынести в один статический метод, как в CallWebhookEventAdmin
    @staticmethod
    def _as_pretty_json(value) -> str:
        if value is None:
            return mark_safe("<pre style='color:#888'>null</pre>")
        try:
            rendered = json.dumps(value, ensure_ascii=False, indent=2)
            return mark_safe(f"<pre style='white-space:pre-wrap; max-width:960px; background:#f8f9fa; padding:8px; border-radius:4px;'>{rendered}</pre>")
        except (TypeError, ValueError):
            return mark_safe(f"<pre style='color:#c00'>Cannot serialize value: {repr(value)}</pre>")