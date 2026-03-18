from django.contrib import admin
from django.utils.safestring import mark_safe
import json

from communications.models import CallProcessingLog, CallWebhookEvent, ProcessedCallArchive


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

class ArchiveDBModelAdmin(admin.ModelAdmin):
    """
    ModelAdmin, который заставляет все операции читать/писать в базу 'archive'.
    Для просмотра достаточно переопределить только get_queryset и несколько других методов.
    Запись (add/change/delete) можно отключить, если архив только для чтения.
    """
    # Название базы данных (должно совпадать с ключом в settings.DATABASES)
    using = 'archive'

    def get_queryset(self, request):
        # Все запросы списка объектов идём в нужную базу
        return super().get_queryset(request).using(self.using)

    def get_form(self, request, obj=None, **kwargs):
        # Если вдруг кто-то попытается редактировать — тоже укажем базу
        form = super().get_form(request, obj, **kwargs)
        form._meta.model.objects = form._meta.model.objects.using(self.using)
        return form

    # Отключаем возможность добавления/изменения/удаления (архив read-only)
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ProcessedCallArchive, site=admin.site)
class ProcessedCallArchiveAdmin(ArchiveDBModelAdmin):
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
        "transcript",
        "analysis",
        "source_payload",
    )
    ordering = ("-created_at",)
    # Показываем JSON-поля красиво (как у вас уже сделано для других моделей)
    def pretty_transcript(self, obj):
        import json
        from django.utils.safestring import mark_safe
        rendered = json.dumps(obj.transcript, ensure_ascii=False, indent=2)
        return mark_safe(f"<pre style='white-space:pre-wrap;max-width:900px'>{rendered}</pre>")
    pretty_transcript.short_description = "Transcript"

    def pretty_analysis(self, obj):
        import json
        from django.utils.safestring import mark_safe
        rendered = json.dumps(obj.analysis, ensure_ascii=False, indent=2)
        return mark_safe(f"<pre style='white-space:pre-wrap;max-width:900px'>{rendered}</pre>")
    pretty_analysis.short_description = "Analysis"

    def pretty_source_payload(self, obj):
        import json
        from django.utils.safestring import mark_safe
        rendered = json.dumps(obj.source_payload, ensure_ascii=False, indent=2)
        return mark_safe(f"<pre style='white-space:pre-wrap;max-width:900px'>{rendered}</pre>")
    pretty_source_payload.short_description = "Source Payload"

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