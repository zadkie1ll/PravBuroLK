from fastapi import Header, HTTPException

from .config import settings


def verify_internal_token(authorization: str = Header(default="")) -> None:
    """Простая защита общим секретом для сервис-сервис вызовов.
    Если internal_token не задан — эндпоинт открыт (только для локального прототипа),
    зеркалит _check_internal_token из leadreport/views.py."""
    if not settings.internal_token:
        return
    provided = authorization.removeprefix("Bearer ").strip()
    if provided != settings.internal_token:
        raise HTTPException(status_code=403, detail="invalid internal token")
