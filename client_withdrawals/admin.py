from django.contrib import admin

from .models import ClientWithdrawalRecord


@admin.register(ClientWithdrawalRecord)
class ClientWithdrawalRecordAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "client",
        "withdrawal_date",
        "transfer_date",
        "withdrawal_amount",
        "transferred_amount",
        "tail_amount",
        "created_at",
    )
    list_filter = ("withdrawal_date", "transfer_date", "created_at")
    search_fields = (
        "client__surname",
        "client__name",
        "client__middlename",
        "client__bitrix_id",
    )

