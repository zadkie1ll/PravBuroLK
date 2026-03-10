from django.contrib import admin
from django.utils.html import format_html_join
from django.utils.safestring import mark_safe
from simple_history.admin import SimpleHistoryAdmin  # 👈 добавляем историю
from payments.models import (
    Contract,
    InstallmentPlan,
    InstallmentPayment,
    ActualPayment,
    OtherPayment,
    PaymentApplication,
)
from clients.models import (
    Client,
    StageTemplate,
    ReferralClick,
    Application,
    Employee,
)
from .models import Prize, Ticket, SpinResult
from education_platform.models import TraineeProfile
from bitrix.models import Region, PmRate

from django.contrib import admin, messages
from django.urls import path
from django.shortcuts import redirect
from django.conf import settings
import requests
from bitrix.services.regions_sync import sync_regions_from_bitrix_logic



class ContractInline(admin.TabularInline):
    model = Contract
    extra = 0
    readonly_fields = ('created_at',)


class OtherPaymentInline(admin.TabularInline):
    model = OtherPayment
    extra = 0
    readonly_fields = ('created_at', 'paid_at')


@admin.register(Client)
class ClientAdmin(SimpleHistoryAdmin):  # 👈 история включена
    list_display = (
        'id', 'surname', 'name', 'middlename', 'bitrix_id', 'user',
        'stage', 'referral_code', 'deal_id'
        'need_stage_popup',       
        'stage_popup_shown',      
    )
    search_fields = ('surname', 'name', 'middlename', 'bitrix_id', 'user__username', 'referral_code')
    list_filter = ('bitrix_id', 'stage')
    ordering = ('surname', 'name')
    readonly_fields = ('referral_code', 'installment_payments_list', 'deal_id')
    inlines = [ContractInline, OtherPaymentInline]
    history_list_display = ['stage', 'user']  # 👈 доп. поля в истории

    fieldsets = (
        (None, {
            "fields": (
                'surname', 'name', 'middlename', 'bitrix_id', 'user',
                'stage', 'referral_code', 'deal_id'
                'need_stage_popup', 'stage_popup_shown',
                'acquiring_enabled',   # ← добавлено
            ),
        }),
        ("Платежи по рассрочке", {
            "fields": ('installment_payments_list',),
        }),
    )

    def installment_payments_list(self, obj):
        payments = InstallmentPayment.objects.filter(plan__contract__client=obj).select_related("plan")
        if not payments.exists():
            return "Нет платежей"
        rows = [
            (p.plan_id, p.number, p.due_date, p.amount_due, p.amount_paid, p.get_status_display())
            for p in payments
        ]
        return format_html_join(
            "\n",
            "<div>План #{0}, Платеж {1}: дата {2}, к оплате {3}, оплачено {4}, статус {5}</div>",
            rows
        )
    installment_payments_list.short_description = "Платежи по рассрочке"
    installment_payments_list.allow_tags = True


@admin.register(StageTemplate)
class StageTemplateAdmin(SimpleHistoryAdmin):  # 👈 история включена
    list_display = ('id', 'name', 'slug', 'order', 'description')
    ordering = ('order',)
    search_fields = ('name', 'slug', 'description')

    def short_description(self, obj):
        if obj.description:
            return obj.description[:50] + ("…" if len(obj.description) > 50 else "")
        return "-"
    short_description.short_description = "Описание"


class InstallmentPaymentInline(admin.TabularInline):
    model = InstallmentPayment
    extra = 0


class PaymentApplicationInline(admin.TabularInline):
    model = PaymentApplication
    extra = 0
    readonly_fields = ('applied_amount', 'created_at')


@admin.register(Contract)
class ContractAdmin(SimpleHistoryAdmin):  # 👈 история включена
    list_display = ('id', 'client', 'total_amount', 'discount', 'first_payment',
                    'first_payment_date', 'number_of_payments', 'created_at')
    search_fields = ('client__surname', 'client__name', 'client__bitrix_id')
    list_filter = ('created_at',)
    ordering = ('-created_at',)


@admin.register(InstallmentPlan)
class InstallmentPlanAdmin(SimpleHistoryAdmin):  # 👈 история включена
    list_display = ('id', 'contract', 'created_at', 'calculated')
    inlines = [InstallmentPaymentInline]
    list_filter = ('calculated',)
    ordering = ('-created_at',)
    search_fields = (
        'id',
        'contract__client__surname',
        'contract__client__name',
        'contract__client__bitrix_id',
        'contract__id',
    )


@admin.register(InstallmentPayment)
class InstallmentPaymentAdmin(SimpleHistoryAdmin):  # 👈 история включена
    list_display = ('id', 'plan', 'number', 'due_date', 'amount_due', 'amount_paid', 'status')
    list_filter = ('status', 'due_date')
    ordering = ('due_date',)
    inlines = [PaymentApplicationInline]
    search_fields = (
        'id',
        'plan__id',
        'plan__contract__id',
        'plan__contract__client__surname',
        'plan__contract__client__name',
        'plan__contract__client__bitrix_id',
        'number',
    )


@admin.register(ActualPayment)
class ActualPaymentAdmin(SimpleHistoryAdmin):  # 👈 история включена
    list_display = ("id", "plan", "payment_date", "amount")  
    ordering = ("-payment_date",)  
    list_filter = ("payment_date",)
    search_fields = (
        'plan__contract__client__surname',
        'plan__contract__client__name',
        'plan__contract__client__middlename',
        'plan__contract__client__bitrix_id',
    ) 


@admin.register(OtherPayment)
class OtherPaymentAdmin(SimpleHistoryAdmin):  # 👈 история включена
    list_display = ('id', 'client', 'payment_type', 'amount', 'is_paid', 'created_at', 'paid_at')
    list_filter = ('payment_type', 'is_paid')
    search_fields = ('client__surname', 'client__bitrix_id')
    ordering = ('-created_at',)


@admin.register(Employee)
class EmployeeAdmin(SimpleHistoryAdmin):  # 👈 история включена
    list_display = ("id", "name", "bitrix_id", "referral_code", 'deal_id' "updated_at")
    search_fields = ("name", "bitrix_id", "referral_code")
    readonly_fields = ("referral_code", "updated_at")
    ordering = ("name",)
    
    
    
@admin.register(Prize)
class PrizeAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "chance",
        "is_active",
        "created_at",
    )

    list_editable = (
        "chance",
        "is_active",
    )

    list_filter = (
        "is_active",
        "created_at",
    )

    search_fields = (
        "name",
    )

    ordering = (
        "-created_at",
    )

@admin.register(SpinResult)
class SpinResultAdmin(admin.ModelAdmin):
    list_display = ("ticket", "prize", "is_win", "created_at")
    list_filter = ("is_win", "prize")
    search_fields = ("ticket__code",)

@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "is_used",
        "used_at",
        "created_at",
    )

    list_filter = (
        "is_used",
        "created_at",
    )

    search_fields = (
        "code",
    )

    ordering = (
        "-created_at",
    )

    readonly_fields = (
        "used_at",
        "created_at",
    )
    
    
    
@admin.register(TraineeProfile)
class TraineeProfileAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "birthday",
        "started_at",
        "is_active",
        "created_at",
    )

    list_select_related = ("user",)

    search_fields = (
        "user__username",
        "user__first_name",
        "user__last_name",
        "user__email",
    )

    list_filter = (
        "is_active",
        "started_at",
        "created_at",
    )

    ordering = ("-created_at",)

    readonly_fields = ("created_at", "updated_at")
    
    
@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ("name", "bitrix_region_id", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name", "bitrix_region_id")
    ordering = ("name",)
    change_list_template = "admin/regions_changelist.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "sync-from-bitrix/",
                self.admin_site.admin_view(self.sync_from_bitrix),
                name="sync_regions_from_bitrix",
            ),
        ]
        return custom_urls + urls

    def sync_from_bitrix(self, request):
        try:
            data = sync_regions_from_bitrix_logic()
            self.message_user(
                request,
                f"Синхронизация завершена: "
                f"создано {data.get('created', 0)}, "
                f"обновлено {data.get('updated', 0)}, "
                f"деактивировано {data.get('deactivated', 0)}",
                level=messages.SUCCESS,
            )
        except Exception as e:
            self.message_user(request, f"Ошибка синхронизации регионов: {e}", level=messages.ERROR)

        return redirect("..")


@admin.register(PmRate)
class PmRateAdmin(admin.ModelAdmin):
    list_display = ("region", "effective_from", "pm_working", "pm_pensioner", "pm_child", "updated_at")
    list_filter = ("region", "effective_from")
    search_fields = ("region__name", "region__bitrix_region_id")
    ordering = ("region__name", "-effective_from")