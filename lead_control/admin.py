from django.contrib import admin, messages
from django.http import HttpRequest, HttpResponseRedirect
from django.urls import path, reverse
from django.utils.html import format_html

from .models import LeadMonitor
from .services import process_all_active_monitors, process_monitor


@admin.register(LeadMonitor)
class LeadMonitorAdmin(admin.ModelAdmin):
    change_list_template = "admin/lead_control/leadmonitor/change_list.html"
    list_display = (
        "id",
        "bitrix_deal_link",
        "status",
        "is_active",
        "responsible_bitrix_user_id",
        "bitrix_task_id",
        "attempts_today",
        "attempts_total",
        "last_checked_at",
        "updated_at",
    )
    list_filter = ("status", "is_active", "current_stage_id", "created_at", "updated_at")
    search_fields = ("bitrix_deal_id", "bitrix_task_id", "responsible_bitrix_user_id")
    readonly_fields = ("created_at", "updated_at", "last_checked_at", "raw_deal_data")
    actions = ("run_selected_monitors",)

    fieldsets = (
        ("Bitrix", {
            "fields": (
                "bitrix_deal_id",
                "initial_bitrix_task_id",
                "bitrix_task_id",
                "moderator_bitrix_user_id",
                "responsible_bitrix_user_id",
                "task_description",
                "raw_deal_data",
            ),
        }),
        ("Статус", {
            "fields": (
                "is_active",
                "status",
                "status_comment",
                "current_stage_id",
            ),
        }),
        ("Попытки", {
            "fields": (
                "initial_task_created",
                "attempts_total",
                "attempts_today",
                "attempts_last_reset_date",
                "entered_logic_at",
                "last_task_closed_at",
                "last_checked_at",
            ),
        }),
        ("Служебное", {
            "fields": ("created_at", "updated_at"),
        }),
    )

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "run-service/",
                self.admin_site.admin_view(self.run_service_view),
                name="lead_control_leadmonitor_run_service",
            ),
        ]
        return custom_urls + urls

    @admin.action(description="Запустить обработку выбранных мониторингов")
    def run_selected_monitors(self, request: HttpRequest, queryset):
        stats = {
            "total": 0,
            "success": 0,
            "skipped": 0,
            "waiting_task": 0,
            "waiting_time": 0,
            "task_created": 0,
            "error": 0,
        }

        for monitor in queryset.order_by("id"):
            stats["total"] += 1
            result = process_monitor(monitor)
            if result in stats:
                stats[result] += 1

        self.message_user(
            request,
            (
                "Выбранные мониторинги обработаны. "
                f"Всего: {stats['total']}, создано задач: {stats['task_created']}, "
                f"ожидают задачу: {stats['waiting_task']}, ожидают время: {stats['waiting_time']}, "
                f"успешно: {stats['success']}, пропущено: {stats['skipped']}, ошибок: {stats['error']}."
            ),
            level=messages.INFO,
        )

    def run_service_view(self, request: HttpRequest):
        if request.method != "POST":
            changelist_url = reverse("admin:lead_control_leadmonitor_changelist")
            self.message_user(
                request,
                "Ручной запуск сервиса должен выполняться через POST.",
                level=messages.WARNING,
            )
            return HttpResponseRedirect(changelist_url)

        stats = process_all_active_monitors()
        self.message_user(
            request,
            (
                "Сервис lead_control запущен вручную. "
                f"Всего: {stats['total']}, создано задач: {stats['task_created']}, "
                f"ожидают задачу: {stats['waiting_task']}, ожидают время: {stats['waiting_time']}, "
                f"успешно: {stats['success']}, пропущено: {stats['skipped']}, ошибок: {stats['error']}."
            ),
            level=messages.SUCCESS if not stats["error"] else messages.WARNING,
        )
        return HttpResponseRedirect(reverse("admin:lead_control_leadmonitor_changelist"))

    @admin.display(description="Сделка")
    def bitrix_deal_link(self, obj: LeadMonitor):
        if not obj.bitrix_deal_id:
            return "-"
        return format_html(
            '<a href="https://prav-buro.bitrix24.ru/crm/deal/details/{}/" target="_blank">{}</a>',
            obj.bitrix_deal_id,
            obj.bitrix_deal_id,
        )
