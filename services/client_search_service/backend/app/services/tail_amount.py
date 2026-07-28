from decimal import Decimal

import requests

from ..config import settings


def get_total_tail_amount(client_id: int) -> Decimal:
    """Читает internal-эндпоинт монолита (client_withdrawals/views.py:
    internal_client_tail_amount) — сам client_withdrawals пока не вынесен, это единственная
    точка чтения без переноса всего модуля. Недоступность монолита не должна ронять
    карточку клиента — тихо возвращаем 0."""
    url = f"{settings.monolith_internal_base_url}/api/internal/clients/{client_id}/tail-amount/"
    headers = {"Authorization": f"Bearer {settings.monolith_internal_token}"} if settings.monolith_internal_token else {}
    try:
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status()
        return Decimal(response.json()["total_tail_amount"])
    except Exception:
        return Decimal("0")
