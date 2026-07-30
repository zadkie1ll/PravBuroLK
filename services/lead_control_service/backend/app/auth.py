from fastapi import Header, HTTPException

from .config import settings


def verify_internal_token(authorization: str = Header(default="")) -> None:
    """Общий секрет для монолита, вызывающего внутренние эндпоинты этого сервиса
    (зеркалит client_withdrawals/views.py:_check_internal_token). Если токен не задан —
    эндпоинт открыт (только для локального прототипа)."""
    if not settings.internal_api_token:
        return
    provided = authorization.removeprefix("Bearer ").strip()
    if provided != settings.internal_api_token:
        raise HTTPException(status_code=403, detail="invalid internal token")
