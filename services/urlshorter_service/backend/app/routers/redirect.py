from __future__ import annotations

from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Click, UrlShortener

router = APIRouter(tags=["redirect"])

# Сетевой ретрай (браузер, прокси, бот-префетч мессенджера) бьёт по тому же GET
# почти мгновенно — в отличие от настоящего повторного захода тем же человеком.
# Схлопываем такие повторы в одно окно, чтобы не задваивать клики в статистике.
CLICK_DEDUP_WINDOW = timedelta(seconds=3)


@router.get("/url")
def generate_url(request: Request, source: str | None = None, social: str = "", db: Session = Depends(get_db)):
    """Порт urlshorter/views.py:generate_url. Публичный эндпоинт — реальные пользователи
    переходят сюда по коротким ссылкам из соцсетей, авторизация не нужна.

    Расхождение с монолитом: при отсутствии `source` там был редирект на Django `index`
    (страница монолита, не имеющая смысла в контексте отдельного сервиса) — здесь просто 400."""
    if not source:
        raise HTTPException(status_code=400, detail="source is required")

    obj = db.query(UrlShortener).filter(UrlShortener.source == source).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Источник не найден")

    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    is_retry = (
        db.query(Click.id)
        .filter(
            Click.url_id == obj.id,
            Click.ip_address == ip_address,
            Click.user_agent == user_agent,
            Click.clicked_at >= datetime.now(timezone.utc) - CLICK_DEDUP_WINDOW,
        )
        .first()
        is not None
    )
    if not is_retry:
        db.add(
            Click(
                url_id=obj.id,
                social=social or None,
                ip_address=ip_address,
                user_agent=user_agent,
            )
        )
        db.commit()

    utm_params = {
        "utm_source": social or "unknown",
        "utm_medium": "social",
        "utm_campaign": source,
    }
    destination_with_utm = f"{obj.destination}?{urlencode(utm_params)}"

    return RedirectResponse(destination_with_utm, status_code=302)
