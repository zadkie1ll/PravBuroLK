# app/admin.py
from django.contrib import admin
from django.utils.html import format_html

from .models import LeadSource, LeadEntry, SalesManager, IssuedCredentialLog
from django.contrib import admin, messages
from django.urls import path
from django.shortcuts import redirect
from django.utils.html import format_html
from .services.sources_sync import sync_sources_from_bitrix_logic
from .services.managers_sync import sync_sales_managers_from_bitrix_logic

@admin.register(LeadSource)
class LeadSourceAdmin(admin.ModelAdmin):
    list_display = ("name", "bitrix_id", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "bitrix_id")
    ordering = ("name",)
    list_editable = ("is_active",)
    readonly_fields = ("created_at",)

    change_list_template = "admin/leads/leadsource/change_list.html"  

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "sync-from-bitrix/",
                self.admin_site.admin_view(self.sync_from_bitrix_view),
                name="leadsource-sync-from-bitrix",
            ),
        ]
        return custom_urls + urls

    def sync_from_bitrix_view(self, request):
        """
        Запускается по кнопке в админке.
        """
        try:
            result = sync_sources_from_bitrix_logic()

            # Красиво покажем итог в админке
            messages.success(
                request,
                (
                    f"Синхронизация источников завершена. "
                    f"Из Bitrix: {result.get('total_from_bitrix')}. "
                    f"Создано: {result.get('created')}, "
                    f"Обновлено: {result.get('updated')}, "
                    f"Деактивировано: {result.get('deactivated')}."
                ),
            )
        except Exception as exc:
            messages.error(request, f"Ошибка синхронизации источников: {exc}")

        return redirect("..")  # обратно на список источников


@admin.register(LeadEntry)
class LeadEntryAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "occurred_at",
        "manager",
        "source",
        "bitrix_lead_id",
        "short_comment",
        "created_at",
    )
    list_select_related = ("manager", "source")
    list_filter = ("source", "manager")
    date_hierarchy = "occurred_at"
    ordering = ("-occurred_at", "-id")
    list_per_page = 50

    search_fields = (
        "id",
        "comment",
        "source__name",
        "manager__username",
        "manager__email",
        "bitrix_lead_id",
    )

    autocomplete_fields = ("source", "manager") 
    raw_id_fields = ()  
    readonly_fields = ("created_at",)

    fieldsets = (
        (None, {"fields": ("manager", "occurred_at", "source")}),
        ("Комментарий", {"fields": ("comment",)}),
        ("Bitrix24 (на будущее)", {"fields": ("bitrix_lead_id",)}),
        ("Служебное", {"fields": ("created_at",), "classes": ("collapse",)}),
    )

    def short_comment(self, obj: LeadEntry) -> str:
        text = (obj.comment or "").strip()
        if not text:
            return "—"
        return text[:60] + ("…" if len(text) > 60 else "")

    short_comment.short_description = "Комментарий"
    
    
    
    
@admin.register(SalesManager)
class SalesManagerAdmin(admin.ModelAdmin):
    list_display = ("name", "bitrix_user_id", "email", "phone", "user", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name", "email", "user", "phone", "bitrix_user_id")
    ordering = ("name",)
    list_editable = ("is_active",)
    list_per_page = 50

    change_list_template = "admin/leads/salesmanager/change_list.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "sync-from-bitrix/",
                self.admin_site.admin_view(self.sync_from_bitrix_view),
                name="salesmanager-sync-from-bitrix",
            ),
        ]
        return custom_urls + urls

    def sync_from_bitrix_view(self, request):
        try:
            result = sync_sales_managers_from_bitrix_logic()
            messages.success(
                request,
                (
                    "Синхронизация менеджеров завершена. "
                    f"Из Bitrix: {result.get('total_from_bitrix')}. "
                    f"Создано: {result.get('created')}, "
                    f"Обновлено: {result.get('updated')}, "
                    f"Деактивировано: {result.get('deactivated')}."
                ),
            )
        except Exception as exc:
            messages.error(request, f"Ошибка синхронизации менеджеров: {exc}")

        return redirect("..")


@admin.register(IssuedCredentialLog )
class IssuedCredentialLogAdmin(admin.ModelAdmin):
    list_display = ("issued_at", "manager", "username", "password")
    search_fields = ("username", "manager__name")
    list_filter = ("issued_at",)
    ordering = ("-issued_at",)