from django.contrib import admin
from communications.models import CallProcessingLog, CallWebhookEvent


@admin.register(CallWebhookEvent)
class CallWebhookEventAdmin(admin.ModelAdmin):
    list_display = ("id", "event_name", "call_id", "record_file_id", "status", "attempts", "created_at")
    list_filter = ("status", "event_name", "created_at")
    search_fields = ("call_id", "record_file_id")


@admin.register(CallProcessingLog)
class CallProcessingLogAdmin(admin.ModelAdmin):
    list_display = ("id", "event", "level", "message", "created_at")
    list_filter = ("level", "created_at")
    search_fields = ("message",)
