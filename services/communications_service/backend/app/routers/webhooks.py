from __future__ import annotations

import json
import logging
from urllib.parse import parse_qsl

import requests
from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ..config import settings
from ..db import SessionLocal, get_db
from ..models import CallStatus, CallWebhookEvent
from ..services import call_processing

logger = logging.getLogger(__name__)
router = APIRouter(tags=["webhooks"])


def _forward_to_monolith(body: bytes, content_type: str, query_string: str) -> None:
    """Лучшее усилие, без ретраев — если монолит недоступен, событие просто теряется
    для его копии обработки, но собственная обработка в этом сервисе уже прошла успешно."""
    if not settings.bitrix_webhook_forward_url:
        return
    try:
        headers = {"Content-Type": content_type} if content_type else {}
        url = settings.bitrix_webhook_forward_url
        if query_string:
            url = f"{url}?{query_string}"
        requests.post(url, data=body, headers=headers, timeout=15)
    except requests.RequestException:
        logger.warning("bitrix_call_webhook: forward to monolith failed", exc_info=True)


def _process_event_background(event_id: int) -> None:
    db = SessionLocal()
    try:
        call_processing.process_call_event(db, event_id)
    finally:
        db.close()


def _spawn_background_processing(background_tasks: BackgroundTasks, event_id: int) -> None:
    try:
        from ..tasks import process_call_event_task

        process_call_event_task.delay(event_id)
    except Exception:
        logger.exception(
            "Celery dispatch failed for event_id=%s, fallback to in-process background task", event_id
        )
        background_tasks.add_task(_process_event_background, event_id)


async def _extract_payload(request: Request) -> dict:
    content_type = (request.headers.get("content-type") or "").lower()
    if "application/json" in content_type:
        body = await request.body()
        try:
            return json.loads(body.decode("utf-8")) if body else {}
        except json.JSONDecodeError:
            return {}
    form = await request.form()
    return dict(form)


def _extract_payload_bytes(body: bytes, content_type: str) -> dict:
    """Парсит из уже прочитанных байт (а не заново из request.stream()) — тело читается один
    раз в самом начале обработчика, Starlette не даёт прочитать ASGI-поток дважды."""
    if not body:
        return {}
    if "application/json" in content_type:
        try:
            return json.loads(body.decode("utf-8"))
        except json.JSONDecodeError:
            return {}
    return dict(parse_qsl(body.decode("utf-8", errors="ignore")))


@router.post("/bitrix/webhook/call-end")
async def bitrix_call_webhook(request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    try:
        raw_body = await request.body()
        content_type = (request.headers.get("content-type") or "").lower()
        payload = _extract_payload_bytes(raw_body, content_type)

        if settings.bitrix_webhook_forward_url:
            background_tasks.add_task(
                _forward_to_monolith, raw_body, content_type, str(request.query_params)
            )

        event, queued = call_processing.enqueue_call_webhook(db, payload)
        if queued:
            _spawn_background_processing(background_tasks, event.id)

        return JSONResponse(
            {"success": True, "event_id": event.id, "status": event.status, "queued": queued},
            status_code=202,
        )
    except Exception as exc:
        logger.exception("bitrix_call_webhook failed")
        return JSONResponse(
            {"success": False, "error": "webhook_processing_failed", "details": str(exc)},
            status_code=200,
        )


@router.get("/download_call")
def download_call_to_server(
    background_tasks: BackgroundTasks,
    record_file_id: str = Query(...),
    db: Session = Depends(get_db),
):
    try:
        event = CallWebhookEvent(
            event_name="manual_download",
            record_file_id=str(record_file_id),
            raw_payload={"record_file_id": record_file_id, "source": "manual"},
        )
        db.add(event)
        db.commit()
        db.refresh(event)

        _spawn_background_processing(background_tasks, event.id)

        return JSONResponse({"success": True, "event_id": event.id, "status": event.status}, status_code=202)
    except Exception as exc:
        logger.exception("download_call_to_server failed")
        return JSONResponse({"success": False, "error": "manual_download_failed", "details": str(exc)}, status_code=500)


@router.post("/api/manualAnalyze")
async def manual_analyze_last_call(request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    try:
        payload = await _extract_payload(request)

        entity_type = str(payload.get("entity_type", "")).strip().lower()
        entity_id = str(payload.get("entity_id", "")).strip()
        force = bool(payload.get("force", False))

        if not entity_type or not entity_id:
            document_id_parts = [payload.get(f"document_id[{i}]") for i in range(10) if f"document_id[{i}]" in payload]
            if len(document_id_parts) >= 3 and document_id_parts[0] == "crm":
                crm_type = document_id_parts[1]
                raw_id = document_id_parts[2]
                if crm_type == "CCrmDocumentContact":
                    entity_type, entity_id = "contact", raw_id.replace("CONTACT_", "")
                elif crm_type == "CCrmDocumentDeal":
                    entity_type, entity_id = "deal", raw_id.replace("DEAL_", "")
                elif crm_type == "CCrmDocumentLead":
                    entity_type, entity_id = "lead", raw_id.replace("LEAD_", "")

        if not entity_type or not entity_id:
            return JSONResponse(
                {"error": "entity_type и entity_id обязательны (или document_id[] из Bitrix)"}, status_code=400
            )
        if entity_type not in ("lead", "deal", "contact"):
            return JSONResponse({"error": "entity_type должен быть lead/deal/contact"}, status_code=400)

        query = db.query(CallWebhookEvent).filter(
            CallWebhookEvent.status == CallStatus.DONE.value,
            CallWebhookEvent.audio_file_path != "",
        )
        if entity_type == "lead":
            query = query.filter(CallWebhookEvent.lead_id == entity_id)
        elif entity_type == "deal":
            query = query.filter(CallWebhookEvent.deal_id == entity_id)
        else:
            query = query.filter(CallWebhookEvent.contact_id == entity_id)

        event = query.order_by(CallWebhookEvent.created_at.desc(), CallWebhookEvent.id.desc()).first()

        if not event:
            return JSONResponse({"error": f"Не найден завершённый звонок для {entity_type} #{entity_id}"}, status_code=404)

        if not force and isinstance(event.analysis, dict) and event.analysis.get("summary"):
            return JSONResponse(
                {
                    "status": "already_analyzed",
                    "event_id": event.id,
                    "call_id": event.call_id,
                    "analyzed_at": event.updated_at.isoformat(),
                    "summary": event.analysis.get("summary", "—"),
                }
            )

        _spawn_background_processing(background_tasks, event.id)

        return JSONResponse(
            {
                "status": "ok",
                "event_id": event.id,
                "call_id": event.call_id,
                "message": "Задача на переанализ поставлена в фоновую обработку",
                "lead_id": event.lead_id,
                "deal_id": event.deal_id,
                "contact_id": event.contact_id,
            }
        )
    except Exception as exc:
        logger.exception("Ошибка при ручном запуске анализа")
        return JSONResponse({"error": str(exc)}, status_code=500)
