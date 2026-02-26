from django.contrib import admin
from django.utils.safestring import mark_safe
import json

from communications.models import CallProcessingLog, CallWebhookEvent


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

    def pretty_raw_payload(self, obj: CallWebhookEvent) -> str:
        return self._as_pretty_json(obj.raw_payload)

    pretty_raw_payload.short_description = "Raw payload"

    def pretty_transcript(self, obj: CallWebhookEvent) -> str:
        return self._as_pretty_json(obj.transcript)

    pretty_transcript.short_description = "Transcript"

    def pretty_analysis(self, obj: CallWebhookEvent) -> str:
        return self._as_pretty_json(obj.analysis)

    pretty_analysis.short_description = "Analysis"

    @staticmethod
    def _as_pretty_json(value) -> str:
        rendered = json.dumps(value, ensure_ascii=False, indent=2)
        return mark_safe(f"<pre style='white-space:pre-wrap;max-width:900px'>{rendered}</pre>")


@admin.register(CallProcessingLog)
class CallProcessingLogAdmin(admin.ModelAdmin):
    list_display = ("id", "event", "level", "message", "created_at")
    list_filter = ("level", "created_at")
    search_fields = ("message", "event__call_id", "event__lead_id", "event__deal_id", "event__contact_id")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)
