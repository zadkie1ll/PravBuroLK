from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone as dt_timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models import LeadMonitor, LeadMonitorStatus
from ..services import bitrix_lead_control as bitrix
from ..services.bitrix_gateway_client import BitrixAPIError

logger = logging.getLogger(__name__)
router = APIRouter(tags=["webhooks"])


def safe_int(value):
    try:
        if value in (None, "", False):
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


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


def _get_deal_data_from_bitrix(post_data: dict) -> tuple[dict | None, str | None]:
    """Порт bitrix/views.py:get_deal_data_from_bitrix — парсит ID сделки из
    document_id[] Bitrix-автоматизации и тянет саму сделку через gateway."""
    document_id_2 = post_data.get("document_id[2]")
    if not document_id_2:
        return None, "document_id[2] not found"

    deal_id_match = re.search(r"(?:DEAL[_-])?(\d+)", str(document_id_2))
    if not deal_id_match:
        return None, "Invalid deal ID format"

    deal_id = deal_id_match.group(1)

    try:
        deal_data = bitrix.get_deal_by_id(int(deal_id))
    except (BitrixAPIError, ValueError) as exc:
        return None, str(exc)

    return deal_data, None


@router.post("/webhook/deal")
async def deal_webhook_handler(request: Request, db: Session = Depends(get_db)):
    """Порт lead_control.views.deal_webhook_handler."""
    post_data = await _extract_payload(request)

    deal_data, error = _get_deal_data_from_bitrix(post_data)
    if error:
        return JSONResponse({"error": error, "payload_keys": list(post_data.keys())}, status_code=400)
    if not deal_data:
        return JSONResponse({"error": "Empty deal data"}, status_code=400)

    deal_id = safe_int(deal_data.get("ID"))
    if not deal_id:
        return JSONResponse({"error": "Deal ID not found in deal_data"}, status_code=400)

    stage_id = (deal_data.get("STAGE_ID") or "").strip()
    responsible_id = safe_int(deal_data.get("ASSIGNED_BY_ID"))
    moderator_id = safe_int(deal_data.get(settings.lead_control_moderator_field))
    task_description = (deal_data.get(settings.lead_control_task_description_field) or "").strip()

    if not responsible_id:
        return JSONResponse({"error": "ASSIGNED_BY_ID not found in deal_data"}, status_code=400)

    now = datetime.now(dt_timezone.utc)

    try:
        monitor = db.query(LeadMonitor).filter(LeadMonitor.bitrix_deal_id == deal_id).one_or_none()
        created = monitor is None

        if created:
            monitor = LeadMonitor(
                bitrix_deal_id=deal_id,
                moderator_bitrix_user_id=moderator_id,
                responsible_bitrix_user_id=responsible_id,
                task_description=task_description,
                entered_logic_at=now,
                current_stage_id=stage_id,
                is_active=True,
                status=LeadMonitorStatus.NEW.value,
                raw_deal_data=deal_data,
            )
            db.add(monitor)
        else:
            monitor.moderator_bitrix_user_id = moderator_id
            monitor.responsible_bitrix_user_id = responsible_id
            monitor.task_description = task_description
            monitor.current_stage_id = stage_id
            monitor.raw_deal_data = deal_data
            if not monitor.entered_logic_at:
                monitor.entered_logic_at = now

        db.commit()
        db.refresh(monitor)

        # Первую задачу ставим всегда, но только один раз на запись мониторинга
        if not monitor.initial_task_created:
            task_title = f"Прозвонить клиента по сделке #{deal_id}"

            task_id = bitrix.create_bitrix_task(
                title=task_title,
                description=task_description,
                responsible_id=responsible_id,
                auditor_id=moderator_id,
                deal_id=deal_id,
            )

            monitor.initial_bitrix_task_id = task_id
            monitor.bitrix_task_id = task_id
            monitor.initial_task_created = True
            monitor.attempts_total = 1
            monitor.attempts_today = 1
            monitor.attempts_last_reset_date = now.date()
            monitor.status = LeadMonitorStatus.ACTIVE.value
            monitor.status_comment = ""
            db.commit()

        logger.info(
            "Lead registered successfully: deal_id=%s, current_task_id=%s",
            monitor.bitrix_deal_id,
            monitor.bitrix_task_id,
        )

        return JSONResponse({
            "ok": True,
            "created": created,
            "deal_id": monitor.bitrix_deal_id,
            "monitor_id": monitor.id,
            "initial_task_created": monitor.initial_task_created,
            "bitrix_task_id": monitor.bitrix_task_id,
            "status": monitor.status,
            "message": "Deal registered and initial task processed",
        })

    except BitrixAPIError as exc:
        logger.exception("Bitrix task creation error for deal_id=%s", deal_id)
        db.rollback()
        db.query(LeadMonitor).filter(LeadMonitor.bitrix_deal_id == deal_id).update({
            "status": LeadMonitorStatus.ERROR.value,
            "status_comment": f"Ошибка создания первой задачи: {exc}",
        })
        db.commit()
        return JSONResponse(
            {"error": "Bitrix task creation failed", "details": str(exc), "deal_id": deal_id},
            status_code=500,
        )
    except Exception as exc:
        logger.exception("Error while registering deal_id=%s", deal_id)
        db.rollback()
        return JSONResponse({"error": "Internal server error", "details": str(exc)}, status_code=500)
