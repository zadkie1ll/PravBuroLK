from django.contrib import admin

from .models import BitrixSyncLog, CallAttempt, CallQueueItem, CallSession


@admin.register(CallSession)
class CallSessionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "created_by",
        "entity_type",
        "date_from",
        "date_to",
        "status",
        "total_items",
        "processed_items",
        "success_count",
        "failed_count",
        "created_at",
    )
    list_filter = ("entity_type", "status", "created_by", "created_at")
    search_fields = ("id", "created_by__username")
    readonly_fields = ("filters_json", "created_at", "updated_at")


@admin.register(CallQueueItem)
class CallQueueItemAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "session",
        "entity_type",
        "bitrix_entity_id",
        "client_name",
        "phone",
        "status",
        "assigned_to",
        "attempts_count",
        "last_call_result",
        "repeat_unanswered",
        "needs_manual_processing",
        "created_at",
    )
    list_filter = ("status", "assigned_to", "repeat_unanswered", "needs_manual_processing", "created_at")
    search_fields = ("bitrix_entity_id", "client_name", "phone", "responsible_name")
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ("session", "assigned_to")


@admin.register(CallAttempt)
class CallAttemptAdmin(admin.ModelAdmin):
    list_display = ("id", "queue_item", "manager", "result", "started_at", "finished_at", "created_at")
    list_filter = ("result", "manager", "created_at")
    search_fields = ("queue_item__bitrix_entity_id", "comment", "provider_call_id")
    readonly_fields = ("created_at",)
    autocomplete_fields = ("queue_item", "manager")


@admin.register(BitrixSyncLog)
class BitrixSyncLogAdmin(admin.ModelAdmin):
    list_display = ("id", "entity_type", "entity_id", "action", "success", "created_at")
    list_filter = ("entity_type", "action", "success", "created_at")
    search_fields = ("entity_id", "error_text")
    readonly_fields = ("created_at",)
