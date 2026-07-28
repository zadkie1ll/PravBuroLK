from __future__ import annotations

import requests

from ..config import settings


def _register_url() -> str:
    configured = settings.alfa_api_url_prod.strip()
    if configured:
        return configured if configured.endswith(".do") else f"{configured.rstrip('/')}/register.do"
    return "https://payment.alfabank.ru/payment/rest/register.do"


def register_order(order_number: str, amount_kopecks: int, description: str, return_url: str, fail_url: str) -> str:
    """Registers a payment order with Alfa-Bank, returns the hosted payment page URL."""
    payload = {
        "userName": settings.alfa_user_prod.strip(),
        "password": settings.alfa_pass_prod.strip(),
        "orderNumber": order_number,
        "amount": amount_kopecks,
        "description": description,
        "returnUrl": return_url,
        "failUrl": fail_url,
    }

    response = requests.post(_register_url(), data=payload, timeout=15)
    response.raise_for_status()
    data = response.json()

    if data.get("errorCode") and str(data["errorCode"]) != "0":
        raise RuntimeError(data.get("errorMessage") or "Не удалось создать оплату в Альфа-Банке")

    form_url = data.get("formUrl")
    if not form_url:
        raise RuntimeError("Альфа-Банк не вернул ссылку на оплату")
    return form_url
