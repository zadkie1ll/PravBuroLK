import json

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models import BitrixSyncLog

router = APIRouter(prefix="/queue/megafon", tags=["megafon-webhook"])


def _extract_call_id(payload: dict) -> str:
    return str(payload.get("callid") or payload.get("call_id") or payload.get("callId") or payload.get("id") or "")


async def _normalize_payload(request: Request) -> dict:
    """Соответствует normalize_megafon_payload (call_queue/views.py:100) — сперва form-данные,
    иначе пытаемся распарсить JSON-тело."""
    content_type = request.headers.get("content-type", "")
    if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
        form = await request.form()
        if form:
            return dict(form)
    body = await request.body()
    if not body:
        return {}
    try:
        parsed = json.loads(body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {"raw_body": body.decode("utf-8", errors="ignore")}
    return parsed if isinstance(parsed, dict) else {"payload": parsed}


@router.post("/webhook")
async def megafon_webhook(request: Request, db: Session = Depends(get_db)):
    """Соответствует megafon_webhook (call_queue/views.py:1461).
    Публичный эндпоинт — вызывается самим МегаФоном, без нашего JWT."""
    expected_key = settings.megafon_vats_crm_auth_key
    received_key = (
        request.headers.get("X-CRM-AUTH")
        or request.headers.get("X-Megafon-Auth")
        or request.query_params.get("auth")
    )

    payload = await _normalize_payload(request)
    if not received_key:
        received_key = payload.get("crm_token") or payload.get("auth")
    call_id = _extract_call_id(payload)

    if not expected_key or received_key != expected_key:
        db.add(
            BitrixSyncLog(
                entity_type="megafon_webhook",
                entity_id=call_id,
                action="incoming_callback_rejected",
                request_payload={"payload": payload},
                response_payload={"ok": False},
                success=False,
                error_text="Invalid Megafon webhook auth key",
            )
        )
        db.commit()
        return Response(content="Invalid auth key", status_code=403)

    db.add(
        BitrixSyncLog(
            entity_type="megafon_webhook",
            entity_id=call_id,
            action=f"{payload.get('cmd', 'callback')}:{payload.get('type', payload.get('status', 'received'))}",
            request_payload={"payload": payload},
            response_payload={"accepted": True},
            success=True,
        )
    )
    db.commit()
    return {"ok": True}
