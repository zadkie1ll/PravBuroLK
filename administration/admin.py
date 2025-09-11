from django.contrib import admin
from django.utils.html import format_html_join
from django.utils.safestring import mark_safe
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
)


class ContractInline(admin.TabularInline):
    model = Contract
    extra = 0
    readonly_fields = ('created_at',)


class OtherPaymentInline(admin.TabularInline):
    model = OtherPayment
    extra = 0
    readonly_fields = ('created_at', 'paid_at')


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('id', 'surname', 'name', 'middlename', 'bitrix_id', 'user', 'referral_code')
    search_fields = ('surname', 'name', 'middlename', 'bitrix_id', 'user__username', 'referral_code')
    list_filter = ('bitrix_id',)
    ordering = ('surname', 'name')
    readonly_fields = ('referral_code', 'installment_payments_list')
    inlines = [ContractInline, OtherPaymentInline]

    fieldsets = (
        (None, {
            "fields": (
                'surname', 'name', 'middlename', 'bitrix_id', 'user', 'referral_code'
            ),
        }),
        ("Платежи по рассрочке", {
            "fields": ('installment_payments_list',),
        }),
    )

    def installment_payments_list(self, obj):
        """Кастомный блок для просмотра всех платежей клиента по рассрочке"""
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
class StageTemplateAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'order')
    ordering = ('order',)


class InstallmentPaymentInline(admin.TabularInline):
    model = InstallmentPayment
    extra = 0


class PaymentApplicationInline(admin.TabularInline):
    """Inline для отображения распределения платежей"""
    model = PaymentApplication
    extra = 0
    readonly_fields = ('applied_amount', 'created_at')


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display = ('id', 'client', 'total_amount', 'discount', 'first_payment',
                    'first_payment_date', 'number_of_payments', 'created_at')
    search_fields = ('client__surname', 'client__name', 'client__bitrix_id')
    list_filter = ('created_at',)
    ordering = ('-created_at',)


@admin.register(InstallmentPlan)
class InstallmentPlanAdmin(admin.ModelAdmin):
    list_display = ('id', 'contract', 'created_at', 'calculated')
    inlines = [InstallmentPaymentInline]
    list_filter = ('calculated',)
    ordering = ('-created_at',)


@admin.register(InstallmentPayment)
class InstallmentPaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'plan', 'number', 'due_date', 'amount_due', 'amount_paid', 'status')
    list_filter = ('status', 'due_date')
    search_fields = ('plan__contract__client__surname',)
    ordering = ('due_date',)
    inlines = [PaymentApplicationInline]


@admin.register(ActualPayment)
class ActualPaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'contract', 'date', 'amount')
    list_filter = ('date',)
    ordering = ('-date',)
    inlines = [PaymentApplicationInline]


@admin.register(OtherPayment)
class OtherPaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'client', 'payment_type', 'amount', 'is_paid', 'created_at', 'paid_at')
    list_filter = ('payment_type', 'is_paid')
    search_fields = ('client__surname', 'client__bitrix_id')
    ordering = ('-created_at',)


# --- Новые модели реферальной системы ---

@admin.register(ReferralClick)
class ReferralClickAdmin(admin.ModelAdmin):
    list_display = ('id', 'client', 'ip_address', 'user_agent', 'timestamp')
    list_filter = ('timestamp',)
    search_fields = ('client__surname', 'client__bitrix_id', 'ip_address')
    ordering = ('-timestamp',)


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'phone', 'client', 'referral_owner', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('name', 'phone', 'client__surname', 'referral_owner__surname')
    ordering = ('-created_at',)