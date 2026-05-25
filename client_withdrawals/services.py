from decimal import Decimal

from django.conf import settings
from django.db.models import Sum

import requests


def get_withdrawals_page_url(client) -> str:
    base_url = getattr(settings, "SITE_BASE_URL", "https://prav-buro.ru").rstrip("/")
    return f"{base_url}/client-withdrawals/{client.id}/"


def get_total_tail_amount(client) -> Decimal:
    return client.withdrawal_records.aggregate(total=Sum("tail_amount"))["total"] or Decimal("0.00")


def build_withdrawals_summary(client) -> str:
    records = client.withdrawal_records.order_by("-withdrawal_date", "-id")
    if not records.exists():
        return "\n".join(
            [
                "Списания клиента",
                "Записей пока нет.",
                f"Страница: {get_withdrawals_page_url(client)}",
            ]
        )

    header = "Дата снятия | Дата перевода | Снято | Переведено | Хвост"
    separator = "-" * len(header)
    lines = [header, separator]

    for record in records:
        withdrawal_date = record.withdrawal_date.strftime("%d.%m.%Y") if record.withdrawal_date else "-"
        transfer_date = record.transfer_date.strftime("%d.%m.%Y") if record.transfer_date else "-"
        withdrawal_amount = f"{record.withdrawal_amount:.2f}" if record.withdrawal_amount is not None else "-"
        transferred_amount = f"{record.transferred_amount:.2f}" if record.transferred_amount is not None else "-"
        lines.append(
            " | ".join(
                [
                    withdrawal_date,
                    transfer_date,
                    withdrawal_amount,
                    transferred_amount,
                    f"{record.tail_amount:.2f}",
                ]
            )
        )

    return "\n".join(lines)


def build_withdrawals_bitrix_fields(client) -> dict[str, str]:
    return {
        getattr(settings, "BITRIX_CLIENT_WITHDRAWALS_LINK_FIELD", "UF_CRM_1774516783").strip(): get_withdrawals_page_url(client),
        getattr(settings, "BITRIX_CLIENT_WITHDRAWALS_FIELD", "UF_CRM_1774516806").strip(): build_withdrawals_summary(client),
    }


def sync_withdrawals_to_bitrix(client) -> bool:
    if not client.bitrix_id:
        raise ValueError(f"У клиента {client.id} отсутствует bitrix_id")

    webhook_url = getattr(settings, "BITRIX_WEBHOOK_URL", "").rstrip("/")
    if not webhook_url:
        raise ValueError("Не настроен BITRIX_WEBHOOK_URL")

    fields = build_withdrawals_bitrix_fields(client)
    payload = {"id": client.bitrix_id}
    for field_code, value in fields.items():
        if field_code:
            payload[f"fields[{field_code}]"] = value

    response = requests.post(
        f"{webhook_url}/crm.deal.update.json",
        data=payload,
        timeout=15,
    )
    response.raise_for_status()

    data = response.json()
    if not data.get("result"):
        raise ValueError(data.get("error_description") or data.get("error") or "Не удалось обновить Bitrix")

    return True
