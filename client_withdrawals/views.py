from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from clients.models import Client

from .models import ClientWithdrawalRecord
from .services import sync_withdrawals_to_bitrix


@login_required
def client_withdrawals_page(request, client_id):
    client = get_object_or_404(Client, pk=client_id)
    records = client.withdrawal_records.all()

    return render(
        request,
        "client_withdrawals/client_withdrawals_page.html",
        {
            "client": client,
            "records": records,
        },
    )


@login_required
@require_POST
def create_withdrawal_record(request, client_id):
    client = get_object_or_404(Client, pk=client_id)

    try:
        withdrawal_amount = Decimal(request.POST.get("withdrawal_amount", "0").replace(",", "."))
        transferred_amount_raw = (request.POST.get("transferred_amount") or "").strip()
        transferred_amount = (
            Decimal(transferred_amount_raw.replace(",", ".")) if transferred_amount_raw else None
        )
    except InvalidOperation:
        messages.error(request, "Суммы должны быть в числовом формате.")
        return redirect("client_withdrawals_page", client_id=client.id)

    try:
        ClientWithdrawalRecord.objects.create(
            client=client,
            withdrawal_date=request.POST.get("withdrawal_date"),
            transfer_date=request.POST.get("transfer_date") or None,
            withdrawal_amount=withdrawal_amount,
            transferred_amount=transferred_amount,
            comment=request.POST.get("comment", "").strip(),
        )
        try:
            sync_withdrawals_to_bitrix(client)
            messages.success(request, "Запись добавлена и синхронизирована с Битрикс.")
        except Exception as exc:
            messages.warning(request, f"Запись добавлена, но Битрикс не обновлен: {exc}")
    except Exception as exc:
        messages.error(request, f"Не удалось сохранить запись: {exc}")

    return redirect("client_withdrawals_page", client_id=client.id)


@login_required
@require_POST
def update_withdrawal_record(request, record_id):
    record = get_object_or_404(ClientWithdrawalRecord, pk=record_id)
    client = record.client

    try:
        withdrawal_amount = Decimal(request.POST.get("withdrawal_amount", "0").replace(",", "."))
        transferred_amount_raw = (request.POST.get("transferred_amount") or "").strip()
        transferred_amount = (
            Decimal(transferred_amount_raw.replace(",", ".")) if transferred_amount_raw else None
        )
    except InvalidOperation:
        messages.error(request, "Суммы должны быть в числовом формате.")
        return redirect("client_withdrawals_page", client_id=client.id)

    try:
        record.withdrawal_date = request.POST.get("withdrawal_date")
        record.transfer_date = request.POST.get("transfer_date") or None
        record.withdrawal_amount = withdrawal_amount
        record.transferred_amount = transferred_amount
        record.comment = request.POST.get("comment", "").strip()
        record.save()

        try:
            sync_withdrawals_to_bitrix(client)
            messages.success(request, "Запись обновлена и синхронизирована с Битрикс.")
        except Exception as exc:
            messages.warning(request, f"Запись обновлена, но Битрикс не обновлен: {exc}")
    except Exception as exc:
        messages.error(request, f"Не удалось обновить запись: {exc}")

    return redirect("client_withdrawals_page", client_id=client.id)


@login_required
@require_POST
def delete_withdrawal_record(request, record_id):
    record = get_object_or_404(ClientWithdrawalRecord, pk=record_id)
    client = record.client
    record.delete()

    try:
        sync_withdrawals_to_bitrix(client)
        messages.success(request, "Запись удалена и Битрикс обновлен.")
    except Exception as exc:
        messages.warning(request, f"Запись удалена, но Битрикс не обновлен: {exc}")

    return redirect("client_withdrawals_page", client_id=client.id)
