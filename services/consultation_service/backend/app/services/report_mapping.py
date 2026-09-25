from __future__ import annotations

from datetime import datetime
from typing import Any

from ..config import settings

# Редактируемые на этой странице поля отчёта -> поля сделки Bitrix. Подтверждено
# реальным продовым кодом монолита (bitrix/views.py: build_consultation,
# bitrix/generate_template.py) по сделке 16778 — используем те же поля, что уже
# питают старый (некрасивый) вариант этого же отчёта.
REPORT_FIELD_MAP: dict[str, str] = {
    "client": settings.field_client_name,
    "property": settings.field_property,
    "income": settings.field_income,
    "transactions": settings.field_transactions,
    "marriage": settings.field_marriage,
    "children": settings.field_children,
    "contract": settings.field_contract_status,
    "debt": settings.field_debt,
    "cost": settings.field_cost,
    "installment": settings.field_installment,
    "priority": settings.field_priority,
    "summary": settings.field_summary,
    "currentPayment": settings.field_current_payment,
    "included": settings.field_included,
    "extra": settings.field_extra,
    "nextStep": settings.field_next_step,
    "nextDate": settings.field_next_date,
    "documents": settings.field_documents,
}

# "Срок рассрочки" / "Первый платёж и дата" пишет отдельный бот/менеджер при
# оформлении договора (documents_service) — здесь их только показываем,
# редактировать и пересохранять в Bitrix с этой страницы не даём.
# "Итого по графику" на бэкенде вообще не хранится и не отдаётся — это живой
# предпросмотр на фронте (cost - discount + bonus), пересчитывается при вводе.
READ_ONLY_KEYS = ("date", "time", "months", "firstPayment")

# Этих полей физически ещё нет в Bitrix (см. config.py) — форма их показывает и
# даёт заполнить, но при сохранении они пока никуда не пишутся, чтобы не слать
# в Bitrix обновление несуществующего поля. Как только заведут реальные UF_CRM_*
# и подставят в .env — убрать ключ отсюда, и поле начнёт сохраняться как обычно.
PENDING_BITRIX_FIELD_KEYS = (
    "priority",
    "summary",
    "currentPayment",
    "included",
    "extra",
    "nextStep",
    "nextDate",
    "documents",
)


def _stringify(value: Any) -> str:
    if value is None or value is False:
        return ""
    if isinstance(value, list):
        for item in value:
            if item not in (None, ""):
                return str(item)
        return ""
    return str(value)


def _parse_amount(value: Any) -> float | None:
    """Bitrix хранит суммы вида '24600|RUB' — берём число до '|'."""
    raw = _stringify(value)
    if not raw:
        return None
    amount = raw.split("|", 1)[0].strip()
    try:
        return float(amount)
    except ValueError:
        return None


def _format_date(raw: Any) -> str:
    raw = _stringify(raw)
    if not raw:
        return ""
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).strftime("%d.%m.%Y")
    except ValueError:
        return raw


def _format_time(raw: Any) -> str:
    raw = _stringify(raw)
    if not raw:
        return ""
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).strftime("%H:%M МСК")
    except ValueError:
        return ""


def deal_to_report_fields(deal: dict[str, Any]) -> dict[str, str]:
    fields = {report_key: _stringify(deal.get(bitrix_field)) for report_key, bitrix_field in REPORT_FIELD_MAP.items()}

    created = deal.get(settings.field_consultation_date)
    fields["date"] = _format_date(created)
    fields["time"] = _format_time(created)

    months = _parse_amount(deal.get(settings.field_installment_months))
    fields["months"] = f"{int(months)} мес." if months else ""

    first_payment_amount = _parse_amount(deal.get(settings.field_first_payment_amount))
    first_payment_date = _format_date(deal.get(settings.field_first_payment_date))
    if first_payment_amount and first_payment_date:
        fields["firstPayment"] = f"{first_payment_amount:,.0f} ₽ · {first_payment_date}".replace(",", " ")
    else:
        fields["firstPayment"] = ""

    return fields


def computed_values(deal: dict[str, Any]) -> dict[str, float]:
    """Сырые числа для живого предпросмотра "Итого по графику" на фронте —
    считается там же реактивно от текущего (возможно ещё не сохранённого)
    значения "Стоимость услуг", а не только один раз на сервере.
    """
    return {
        "bonusAmount": _parse_amount(deal.get(settings.field_bonus_amount)) or 0,
        "discountAmount": _parse_amount(deal.get(settings.field_discount_amount)) or 0,
    }


def report_fields_to_bitrix(values: dict[str, str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for report_key, value in values.items():
        if report_key in READ_ONLY_KEYS or report_key in PENDING_BITRIX_FIELD_KEYS:
            continue
        bitrix_field = REPORT_FIELD_MAP.get(report_key)
        if bitrix_field:
            result[bitrix_field] = value
    return result


def manager_to_report(user: dict[str, Any]) -> dict[str, str | None]:
    name = " ".join(part for part in [user.get("NAME"), user.get("LAST_NAME")] if part).strip()
    phone = user.get("PERSONAL_MOBILE") or user.get("WORK_PHONE") or user.get("PERSONAL_PHONE") or ""
    return {
        "name": name or None,
        "contact": phone or None,
        "role": "Менеджер",
        "photoUrl": user.get("PHOTO_URL") or None,
    }


def static_links() -> dict[str, str]:
    return {
        "chat": settings.support_chat_url,
        "telegram": settings.telegram_url,
        "vk": settings.vk_url,
        "youtube": settings.youtube_url,
        "yandexMaps": settings.yandex_maps_url,
    }
