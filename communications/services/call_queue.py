import json
import logging
import os
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from django.conf import settings
from dotenv import find_dotenv, load_dotenv

from communications.models import CallProcessingLog, CallWebhookEvent, ProcessedCallArchive

load_dotenv(find_dotenv())

logger = logging.getLogger(__name__)
BITRIX_WEBHOOK = os.getenv("BITRIX_WEBHOOK", "")
MIN_CALL_DURATION_SECONDS = int(os.getenv("MIN_CALL_DURATION_SECONDS", "300"))
BITRIX_STAT_POLL_TIMEOUT_SECONDS = float(os.getenv("BITRIX_STAT_POLL_TIMEOUT_SECONDS", "180"))
BITRIX_STAT_POLL_INTERVAL_SECONDS = float(os.getenv("BITRIX_STAT_POLL_INTERVAL_SECONDS", "3"))
BITRIX_COMMENT_TRANSCRIPT_MAX_CHARS = int(os.getenv("BITRIX_COMMENT_TRANSCRIPT_MAX_CHARS", "12000"))
BITRIX_COMMENT_ANALYSIS_MAX_CHARS = int(os.getenv("BITRIX_COMMENT_ANALYSIS_MAX_CHARS", "8000"))
BITRIX_LEAD_OWNER_TYPE_ID = os.getenv("BITRIX_LEAD_OWNER_TYPE_ID", "2").strip() or "2"
BITRIX_CONTACT_OWNER_TYPE_ID = os.getenv("BITRIX_CONTACT_OWNER_TYPE_ID", "3").strip() or "3"
BITRIX_OWNER_TYPE_TO_ENTITY_TYPE = {
    "1": os.getenv("BITRIX_OWNER_TYPE_1_ENTITY_TYPE", "deal").strip() or "deal",
    "2": os.getenv("BITRIX_OWNER_TYPE_2_ENTITY_TYPE", "lead").strip() or "lead",
    "3": os.getenv("BITRIX_OWNER_TYPE_3_ENTITY_TYPE", "contact").strip() or "contact",
    "4": os.getenv("BITRIX_OWNER_TYPE_4_ENTITY_TYPE", "company").strip() or "company",
}
ALLOWED_CRM_ENTITY_TYPES = {
    item.strip().upper()
    for item in os.getenv("ALLOWED_CRM_ENTITY_TYPES", "").split(",")
    if item.strip()
}


class BitrixWebhookError(Exception):
    pass


def enqueue_call_webhook(payload: dict[str, Any]) -> tuple[CallWebhookEvent, bool]:
    event_name = _extract_event_name(payload)
    call_id = _extract_call_id(payload)
    lead_id = _extract_lead_id(payload)
    contact_id = _extract_contact_id(payload)
    record_file_id = _extract_record_file_id(payload)
    dedupe_key = _build_dedupe_key(payload, event_name, call_id)

    # Если webhook с тем же call_id уже записан, не ставим дубликат в очередь повторно.
    if dedupe_key:
        existing = (
            CallWebhookEvent.objects.exclude(status=CallWebhookEvent.Status.FAILED)
            .filter(dedupe_key=dedupe_key)
            .order_by("-id")
            .first()
        )
        if existing:
            _log(
                existing,
                CallProcessingLog.Level.INFO,
                "Duplicate webhook skipped",
                {"dedupe_key": dedupe_key},
            )
            return existing, False

    should_process, ignore_reason = _should_process_payload(payload, event_name, lead_id)

    event = CallWebhookEvent.objects.create(
        event_name=event_name,
        call_id=call_id,
        lead_id=lead_id,
        contact_id=contact_id,
        record_file_id=record_file_id,
        dedupe_key=dedupe_key,
        raw_payload=payload,
        status=CallWebhookEvent.Status.PENDING if should_process else CallWebhookEvent.Status.IGNORED,
    )
    if should_process:
        _log(event, CallProcessingLog.Level.INFO, "Webhook accepted", _webhook_log_details(payload))
        return event, True

    _log(
        event,
        CallProcessingLog.Level.INFO,
        "Webhook ignored at ingress",
        {"reason": ignore_reason, **_webhook_log_details(payload)},
    )
    return event, False


def process_call_event(event_id: int, raise_on_error: bool = False) -> None:
    try:
        event = CallWebhookEvent.objects.get(id=event_id)
    except CallWebhookEvent.DoesNotExist:
        logger.warning("Event %s not found", event_id)
        return

    if event.status in {CallWebhookEvent.Status.DONE, CallWebhookEvent.Status.IGNORED}:
        return

    event.status = CallWebhookEvent.Status.PROCESSING
    event.attempts += 1
    event.error_message = ""
    event.save(update_fields=["status", "attempts", "error_message", "updated_at"])
    _log(event, CallProcessingLog.Level.INFO, "Processing started")

    try:
        if not _is_call_finished_event(event):
            event.status = CallWebhookEvent.Status.IGNORED
            event.save(update_fields=["status", "updated_at"])
            _log(event, CallProcessingLog.Level.INFO, "Webhook ignored: call is not finished")
            return

        if _is_call_without_recording(event):
            event.status = CallWebhookEvent.Status.IGNORED
            event.save(update_fields=["status", "updated_at"])
            _log(
                event,
                CallProcessingLog.Level.INFO,
                "Webhook ignored: call ended without recording",
                {
                    "call_duration": _payload_value(event.raw_payload, "CALL_DURATION"),
                    "call_failed_code": _payload_value(event.raw_payload, "CALL_FAILED_CODE"),
                },
            )
            return

        duration_seconds = _extract_call_duration_seconds(event.raw_payload)
        if duration_seconds < MIN_CALL_DURATION_SECONDS:
            event.status = CallWebhookEvent.Status.IGNORED
            event.save(update_fields=["status", "updated_at"])
            _log(
                event,
                CallProcessingLog.Level.INFO,
                "Webhook ignored: call is shorter than 5 minutes",
                {"call_duration": duration_seconds, "min_duration": MIN_CALL_DURATION_SECONDS},
            )
            return

        if not event.call_id:
            event.status = CallWebhookEvent.Status.IGNORED
            event.save(update_fields=["status", "updated_at"])
            _log(event, CallProcessingLog.Level.INFO, "Webhook ignored: CALL_ID is absent")
            return

        # Жесткая последовательность обработки:
        # 1) берем CALL_ID из webhook
        # 2) запрашиваем voximplant.statistic.get по exact CALL_ID
        # 3) используем CALL_RECORD_URL из статистики для скачивания записи
        stat: dict[str, Any] = _get_call_stat_by_call_id(event.call_id)
        _log(
            event,
            CallProcessingLog.Level.INFO,
            "Call statistic fetched",
            _stat_log_details(stat),
        )

        crm_entity_type, crm_entity_id = _extract_crm_entity(event.raw_payload, stat)
        if crm_entity_type and ALLOWED_CRM_ENTITY_TYPES and crm_entity_type not in ALLOWED_CRM_ENTITY_TYPES:
            event.status = CallWebhookEvent.Status.IGNORED
            event.save(update_fields=["status", "updated_at"])
            _log(
                event,
                CallProcessingLog.Level.INFO,
                "Webhook ignored: CRM entity type is not allowed",
                {
                    "crm_entity_type": crm_entity_type,
                    "crm_entity_id": crm_entity_id,
                    "allowed_types": sorted(ALLOWED_CRM_ENTITY_TYPES),
                    **_stat_log_details(stat),
                },
            )
            return

        lead_id = event.lead_id or _extract_lead_id(event.raw_payload)
        if not lead_id:
            lead_id = _extract_lead_id_from_stat(stat)
        if not lead_id and crm_entity_type == "LEAD" and crm_entity_id:
            lead_id = crm_entity_id

        contact_id = event.contact_id or _extract_contact_id(event.raw_payload)
        if not contact_id:
            contact_id = _extract_contact_id_from_stat(stat)
        if not contact_id and crm_entity_type == "CONTACT" and crm_entity_id:
            contact_id = crm_entity_id

        deal_id = crm_entity_id if crm_entity_type == "DEAL" and crm_entity_id else ""

        if not lead_id and not deal_id and not contact_id and not crm_entity_id:
            event.status = CallWebhookEvent.Status.IGNORED
            event.save(update_fields=["status", "updated_at"])
            _log(
                event,
                CallProcessingLog.Level.INFO,
                "Webhook ignored: CRM entity is absent",
                _stat_log_details(stat),
            )
            return

        event.lead_id = str(lead_id or "")
        event.deal_id = str(deal_id or "")
        event.contact_id = str(contact_id or "")
        event.save(update_fields=["lead_id", "deal_id", "contact_id", "updated_at"])
        _log(
            event,
            CallProcessingLog.Level.INFO,
            "CRM entity resolved",
            {
                "crm_entity_type": crm_entity_type,
                "crm_entity_id": crm_entity_id,
                "lead_id": lead_id,
                "deal_id": deal_id,
                "contact_id": contact_id,
            },
        )

        stat = _wait_for_call_record_url(event.call_id, initial_stat=stat)
        record_file_id = str(_stat_value(stat, "RECORD_FILE_ID") or "")
        call_record_url = str(_stat_value(stat, "CALL_RECORD_URL") or "")
        if record_file_id:
            event.record_file_id = record_file_id
            event.save(update_fields=["record_file_id", "updated_at"])

        if call_record_url:
            audio_file_path = _download_record_file_by_url(call_record_url, event.call_id)
        else:
            event.status = CallWebhookEvent.Status.IGNORED
            event.save(update_fields=["status", "updated_at"])
            _log(
                event,
                CallProcessingLog.Level.WARNING,
                "Webhook ignored: CALL_RECORD_URL is absent in statistic.get",
                {"call_id": event.call_id, **_stat_log_details(stat)},
            )
            return

        event.audio_file_path = audio_file_path
        event.save(update_fields=["audio_file_path", "updated_at"])
        _log(
            event,
            CallProcessingLog.Level.INFO,
            "Call recording downloaded",
            {"audio_file_path": audio_file_path},
        )

        transcript = _run_transcription(audio_file_path)
        event.transcript = transcript or []
        event.save(update_fields=["transcript", "updated_at"])
        _log(event, CallProcessingLog.Level.INFO, "Call transcription completed", {"segments": len(transcript or [])})

        speaker_map = _run_diarization_on_transcript(transcript or [])
        if speaker_map:
            _log(event, CallProcessingLog.Level.INFO, "Call diarization completed", {"speeches": len(speaker_map)})
        else:
            _log(event, CallProcessingLog.Level.WARNING, "Call diarization returned empty map")

        analysis = _run_analysis_on_transcript(transcript or [], speaker_map=speaker_map)
        if speaker_map:
            analysis["speaker_map"] = speaker_map
        event.analysis = analysis or {}
        event.status = CallWebhookEvent.Status.DONE
        event.save(update_fields=["analysis", "status", "updated_at"])
        _log(event, CallProcessingLog.Level.INFO, "Call analysis completed")

        comment_entity_type, comment_entity_id, owner_type_id = _resolve_comment_entity(event.raw_payload, stat)
        if comment_entity_id:
            _post_call_result_comment(
                entity_type=comment_entity_type,
                entity_id=comment_entity_id,
                owner_type_id=owner_type_id,
                call_id=event.call_id,
                transcript=event.transcript or [],
                analysis=event.analysis or {},
            )
            _log(
                event,
                CallProcessingLog.Level.INFO,
                "CRM comment posted",
                {
                    "entity_type": comment_entity_type,
                    "entity_id": comment_entity_id,
                    "owner_type_id": owner_type_id,
                    "crm_activity_id": _payload_value(event.raw_payload, "CRM_ACTIVITY_ID")
                    or _stat_value(stat, "CRM_ACTIVITY_ID"),
                },
            )
        else:
            _log(
                event,
                CallProcessingLog.Level.WARNING,
                "CRM comment skipped: owner/entity is absent",
                {
                    "crm_entity_type": crm_entity_type,
                    "crm_entity_id": crm_entity_id,
                    "crm_activity_id": _payload_value(event.raw_payload, "CRM_ACTIVITY_ID")
                    or _stat_value(stat, "CRM_ACTIVITY_ID"),
                },
            )

        _archive_processed_event(event)

    except Exception as exc:
        event.status = CallWebhookEvent.Status.FAILED
        event.error_message = str(exc)
        event.save(update_fields=["status", "error_message", "updated_at"])
        _log(
            event,
            CallProcessingLog.Level.ERROR,
            "Processing failed",
            {"error": str(exc), "error_type": type(exc).__name__},
        )
        if raise_on_error:
            raise


def spawn_background_processing(event_id: int) -> None:
    # По умолчанию работаем без Celery/Redis (встроенный sync-режим).
    # Асинхронный режим включается только через COMMUNICATIONS_USE_CELERY=1.
    if not getattr(settings, "COMMUNICATIONS_USE_CELERY", False):
        process_call_event(event_id)
        return

    try:
        # Импорт внутри функции нужен, чтобы избежать циклического импорта:
        # tasks -> call_queue -> tasks.
        from communications.tasks import process_call_event_task

        process_call_event_task.delay(event_id)
    except Exception:
        logger.exception(
            "Celery dispatch failed for event_id=%s, fallback to inline processing",
            event_id,
        )
        process_call_event(event_id)


def process_pending_queue(limit: int = 50) -> int:
    pending = (
        CallWebhookEvent.objects.filter(status=CallWebhookEvent.Status.PENDING)
        .order_by("created_at")[:limit]
    )

    processed = 0
    for event in pending:
        process_call_event(event.id)
        processed += 1

    return processed


def _log(event: CallWebhookEvent, level: str, message: str, details: dict[str, Any] | None = None) -> None:
    payload = details or {}
    CallProcessingLog.objects.create(
        event=event,
        level=level,
        message=message,
        details=payload,
    )
    logger.log(_level_to_logging(level), "event_id=%s %s %s", event.id, message, payload)


def _extract_event_name(payload: dict[str, Any]) -> str:
    return str(
        payload.get("event")
        or payload.get("EVENT")
        or payload.get("EVENT_NAME")
        or payload.get("type")
        or ""
    )


def _extract_call_id(payload: dict[str, Any]) -> str:
    return str(_payload_value(payload, "CALL_ID") or "")


def _extract_record_file_id(payload: dict[str, Any]) -> str:
    return str(_payload_value(payload, "RECORD_FILE_ID") or "")


def _extract_lead_id(payload: dict[str, Any]) -> str:
    direct = _payload_value(payload, "LEAD_ID") or _payload_value(payload, "CRM_LEAD_ID")
    if direct:
        return str(direct)

    owner_type_id = _payload_value(payload, "OWNER_TYPE_ID")
    owner_id = _payload_value(payload, "OWNER_ID")
    if str(owner_type_id or "") == BITRIX_LEAD_OWNER_TYPE_ID and owner_id:
        return str(owner_id)

    entity_type = str(_payload_value(payload, "CRM_ENTITY_TYPE") or _payload_value(payload, "ENTITY_TYPE") or "").upper()
    entity_id = _payload_value(payload, "CRM_ENTITY_ID") or _payload_value(payload, "ENTITY_ID")
    if entity_type == "LEAD" and entity_id:
        return str(entity_id)

    return ""


def _extract_contact_id(payload: dict[str, Any]) -> str:
    direct = _payload_value(payload, "CONTACT_ID") or _payload_value(payload, "CRM_CONTACT_ID")
    if direct:
        return str(direct)

    owner_type_id = _payload_value(payload, "OWNER_TYPE_ID")
    owner_id = _payload_value(payload, "OWNER_ID")
    if str(owner_type_id or "") == BITRIX_CONTACT_OWNER_TYPE_ID and owner_id:
        return str(owner_id)

    entity_type = str(_payload_value(payload, "CRM_ENTITY_TYPE") or _payload_value(payload, "ENTITY_TYPE") or "").upper()
    entity_id = _payload_value(payload, "CRM_ENTITY_ID") or _payload_value(payload, "ENTITY_ID")
    if entity_type == "CONTACT" and entity_id:
        return str(entity_id)

    return ""


def _extract_lead_id_from_stat(stat: dict[str, Any]) -> str:
    entity_type = str(_stat_value(stat, "CRM_ENTITY_TYPE") or "").upper()
    entity_id = _stat_value(stat, "CRM_ENTITY_ID")
    if entity_type == "LEAD" and entity_id:
        return str(entity_id)

    lead_id = _stat_value(stat, "CRM_LEAD_ID")
    if lead_id:
        return str(lead_id)

    return ""


def _extract_contact_id_from_stat(stat: dict[str, Any]) -> str:
    entity_type = str(_stat_value(stat, "CRM_ENTITY_TYPE") or "").upper()
    entity_id = _stat_value(stat, "CRM_ENTITY_ID")
    if entity_type == "CONTACT" and entity_id:
        return str(entity_id)

    contact_id = _stat_value(stat, "CRM_CONTACT_ID")
    if contact_id:
        return str(contact_id)

    return ""


def _extract_crm_entity(payload: dict[str, Any], stat: dict[str, Any]) -> tuple[str, str]:
    # 1) сначала пытаемся взять из webhook-полей
    payload_type = str(
        _payload_value(payload, "CRM_ENTITY_TYPE")
        or _payload_value(payload, "ENTITY_TYPE")
        or ""
    ).upper()
    payload_id = str(
        _payload_value(payload, "CRM_ENTITY_ID")
        or _payload_value(payload, "ENTITY_ID")
        or ""
    )
    if payload_type and payload_id:
        return payload_type, payload_id

    # 2) затем берем из voximplant.statistic.get
    stat_type = str(_stat_value(stat, "CRM_ENTITY_TYPE") or "").upper()
    stat_id = str(_stat_value(stat, "CRM_ENTITY_ID") or "")
    if stat_type and stat_id:
        return stat_type, stat_id

    return "", ""


def _is_call_finished_event(event: CallWebhookEvent) -> bool:
    call_state = _payload_value(event.raw_payload, "CALL_STATE")
    marker_values = [
        event.event_name.lower(),
        str(call_state or "").lower(),
    ]
    joined = " ".join(value for value in marker_values if value)
    if not joined:
        return True

    finished_markers = [
        "onvoximplantcallend",
        "call_end",
        "finished",
        "hangup",
        "end",
    ]
    return any(marker in joined for marker in finished_markers)


def _is_call_without_recording(event: CallWebhookEvent) -> bool:
    duration_raw = _extract_call_duration_seconds(event.raw_payload)
    failed_code = _payload_value(event.raw_payload, "CALL_FAILED_CODE")

    # Для ONVOXIMPLANTCALLEND это частый сценарий:
    # неуспешный/прерванный звонок приходит как завершенный, но записи у него нет.
    return _is_failed_call_code(failed_code) or duration_raw == 0


def _get_call_stat_by_call_id(call_id: str) -> dict[str, Any]:
    if not call_id:
        return {}
    if not BITRIX_WEBHOOK:
        raise BitrixWebhookError("BITRIX_WEBHOOK is not configured")

    url = f"{BITRIX_WEBHOOK.rstrip('/')}/voximplant.statistic.get"
    params = {"FILTER[CALL_ID]": call_id}
    response = requests.get(url, params=params, timeout=20)

    if not response.ok:
        raise BitrixWebhookError(f"Bitrix voximplant.statistic.get failed: {response.text}")

    result = response.json().get("result")
    if isinstance(result, list) and result:
        exact_with_url = [
            row
            for row in result
            if isinstance(row, dict)
            and str(row.get("CALL_ID") or "") == call_id
            and bool(row.get("CALL_RECORD_URL"))
        ]
        if exact_with_url:
            return exact_with_url[0]

        exact_any = [
            row
            for row in result
            if isinstance(row, dict)
            and str(row.get("CALL_ID") or "") == call_id
        ]
        if exact_any:
            return exact_any[0]

        with_url = [row for row in result if isinstance(row, dict) and bool(row.get("CALL_RECORD_URL"))]
        if with_url:
            return with_url[0]

        return result[0] if isinstance(result[0], dict) else {}
    if isinstance(result, dict):
        return result
    return {}


def _wait_for_call_record_url(call_id: str, initial_stat: dict[str, Any] | None = None) -> dict[str, Any]:
    stat = initial_stat or {}
    if _stat_value(stat, "CALL_RECORD_URL"):
        return stat

    deadline = time.time() + BITRIX_STAT_POLL_TIMEOUT_SECONDS
    attempts = 0
    while time.time() < deadline:
        attempts += 1
        stat = _get_call_stat_by_call_id(call_id)
        if _stat_value(stat, "CALL_RECORD_URL"):
            return stat
        time.sleep(BITRIX_STAT_POLL_INTERVAL_SECONDS)

    raise BitrixWebhookError(
        "CALL_RECORD_URL is absent in statistic.get after retries "
        f"(timeout={BITRIX_STAT_POLL_TIMEOUT_SECONDS}s, interval={BITRIX_STAT_POLL_INTERVAL_SECONDS}s, attempts={attempts})"
    )


def _resolve_comment_entity(payload: dict[str, Any], stat: dict[str, Any]) -> tuple[str, str, str]:
    payload_entity_type = str(_payload_value(payload, "CRM_ENTITY_TYPE") or _payload_value(payload, "ENTITY_TYPE") or "").strip()
    payload_entity_id = _payload_value(payload, "CRM_ENTITY_ID") or _payload_value(payload, "ENTITY_ID")
    payload_owner_type_id = str(_payload_value(payload, "OWNER_TYPE_ID") or "").strip()
    if payload_entity_type and payload_entity_id:
        return payload_entity_type.lower(), str(payload_entity_id), payload_owner_type_id

    stat_entity_type = str(_stat_value(stat, "CRM_ENTITY_TYPE") or "").strip()
    stat_entity_id = _stat_value(stat, "CRM_ENTITY_ID")
    stat_owner_type_id = str(_stat_value(stat, "OWNER_TYPE_ID") or "").strip()
    if stat_entity_type and stat_entity_id:
        return stat_entity_type.lower(), str(stat_entity_id), stat_owner_type_id

    payload_owner_id = _payload_value(payload, "OWNER_ID")
    if payload_owner_type_id and payload_owner_id:
        return _owner_type_to_entity_type(payload_owner_type_id), str(payload_owner_id), payload_owner_type_id

    stat_owner_id = _stat_value(stat, "OWNER_ID")
    if stat_owner_type_id and stat_owner_id:
        return _owner_type_to_entity_type(stat_owner_type_id), str(stat_owner_id), stat_owner_type_id

    return "", "", ""


def _owner_type_to_entity_type(owner_type_id: str) -> str:
    key = str(owner_type_id or "").strip()
    mapped = BITRIX_OWNER_TYPE_TO_ENTITY_TYPE.get(key)
    if mapped:
        return mapped.lower()
    return ""


def _post_call_result_comment(
    entity_type: str,
    entity_id: str,
    owner_type_id: str,
    call_id: str,
    transcript: list[Any],
    analysis: dict[str, Any],
) -> None:
    if not BITRIX_WEBHOOK:
        raise BitrixWebhookError("BITRIX_WEBHOOK is not configured")

    transcript_text = _format_transcript_for_comment(transcript, analysis.get("speaker_map"))
    summary_text = _format_summary_for_comment(analysis)
    quality_text = _format_quality_for_comment(analysis)
    comment = (
        "Автоанализ звонка\n"
        f"CALL_ID: {call_id or '-'}\n\n"
        "1. Summary\n"
        f"{summary_text}\n\n"
        "2. Оценка качества обслуживания\n"
        f"{quality_text}\n\n"
        "3. Транскрибция\n"
        f"{transcript_text}"
    )

    url = f"{BITRIX_WEBHOOK.rstrip('/')}/crm.timeline.comment.add"
    payload: dict[str, Any] = {
        "fields[ENTITY_ID]": str(entity_id),
        "fields[COMMENT]": comment,
    }
    if entity_type:
        payload["fields[ENTITY_TYPE]"] = entity_type.lower()
    if owner_type_id:
        payload["fields[ENTITY_TYPE_ID]"] = str(owner_type_id)

    response = requests.post(url, data=payload, timeout=20)
    if not response.ok:
        raise BitrixWebhookError(f"Failed to add timeline comment: {response.text}")

    payload = response.json()
    if payload.get("error"):
        raise BitrixWebhookError(
            f"Failed to add timeline comment: {payload.get('error_description') or payload.get('error')}"
        )


def _format_transcript_for_comment(transcript: list[Any], speaker_map: dict[str, Any] | None = None) -> str:
    if not transcript:
        return "-"

    normalized_speaker_map = speaker_map if isinstance(speaker_map, dict) else {}
    lines: list[str] = []
    for item in transcript:
        if isinstance(item, dict):
            text = str(item.get("text") or item.get("TEXT") or "").strip()
            start = _coerce_seconds(item.get("start") or item.get("start_seconds"))
            stamp = _seconds_to_mmss(start)
            role = str(normalized_speaker_map.get(stamp) or "unknown")
            if text:
                lines.append(f"{_format_role_label(role)}: {text}" if role != "unknown" else text)
                continue
        if isinstance(item, list) and len(item) >= 2:
            text = str(item[0] or "").strip()
            start = _coerce_seconds(item[1])
            stamp = _seconds_to_mmss(start)
            role = str(normalized_speaker_map.get(stamp) or "unknown")
            if text:
                lines.append(f"{_format_role_label(role)}: {text}" if role != "unknown" else text)
                continue
        text = str(item or "").strip()
        if text:
            lines.append(text)

    merged = "\n".join(lines).strip()
    if not merged:
        return "-"
    if len(merged) > BITRIX_COMMENT_TRANSCRIPT_MAX_CHARS:
        return f"{merged[:BITRIX_COMMENT_TRANSCRIPT_MAX_CHARS].rstrip()}\n...[обрезано]"
    return merged


def _format_summary_for_comment(analysis: dict[str, Any]) -> str:
    if not analysis:
        return "-"

    candidates = [
        analysis.get("summary"),
        analysis.get("short_summary"),
        analysis.get("result"),
    ]
    for value in candidates:
        text = str(value or "").strip()
        if text:
            return text[:BITRIX_COMMENT_ANALYSIS_MAX_CHARS]

    recommendations = analysis.get("recommendations")
    if isinstance(recommendations, list) and recommendations:
        text = "; ".join(str(item).strip() for item in recommendations if str(item).strip())
        if text:
            return text[:BITRIX_COMMENT_ANALYSIS_MAX_CHARS]
    return "-"


def _format_quality_for_comment(analysis: dict[str, Any]) -> str:
    if not analysis:
        return "-"

    score = analysis.get("score")
    score_text = str(score).strip() if score is not None else "-"
    checks = [
        ("Имя использовано", _to_yes_no(analysis.get("name_used"))),
        ("Выявлена боль клиента", _to_yes_no(analysis.get("pain_identified"))),
        ("Предложено решение", _to_yes_no(analysis.get("solution_offered"))),
        ("Приглашение в чат", _to_yes_no(analysis.get("chat_invite"))),
        ("Согласован следующий шаг", _to_yes_no(analysis.get("next_step_agreed"))),
    ]

    mistakes = analysis.get("mistakes")
    mistakes_text = "-"
    if isinstance(mistakes, list):
        cleaned = [str(item).strip() for item in mistakes if str(item).strip()]
        if cleaned:
            mistakes_text = "; ".join(cleaned)

    recommendations = analysis.get("recommendations")
    recommendations_text = "-"
    if isinstance(recommendations, list):
        cleaned = [str(item).strip() for item in recommendations if str(item).strip()]
        if cleaned:
            recommendations_text = "; ".join(cleaned)

    lines = [f"Score: {score_text}/5"]
    lines.extend(f"- {label}: {value}" for label, value in checks)
    lines.append(f"- Ошибки: {mistakes_text}")
    lines.append(f"- Рекомендации: {recommendations_text}")
    rendered = "\n".join(lines).strip()
    if len(rendered) > BITRIX_COMMENT_ANALYSIS_MAX_CHARS:
        return f"{rendered[:BITRIX_COMMENT_ANALYSIS_MAX_CHARS].rstrip()}\n...[обрезано]"
    return rendered


def _format_role_label(role: str) -> str:
    normalized = str(role or "").strip().lower()
    if normalized == "operator":
        return "Оператор"
    if normalized == "client":
        return "Клиент"
    return "Неизвестный"


def _to_yes_no(value: Any) -> str:
    if value is True:
        return "Да"
    if value is False:
        return "Нет"
    return "-"


def _run_diarization_on_transcript(transcript: list[Any]) -> dict[str, str]:
    try:
        from communications.components.ai import diarize_transcript
    except Exception as exc:
        raise RuntimeError(f"Diarization dependencies are unavailable: {exc}") from exc

    try:
        mapping = diarize_transcript(transcript)
    except Exception as exc:
        raise RuntimeError(f"Diarization failed: {exc}") from exc

    if isinstance(mapping, dict):
        cleaned: dict[str, str] = {}
        for k, v in mapping.items():
            key = str(k or "").strip()
            value = str(v or "").strip().lower()
            if key and value:
                cleaned[key] = value
        return cleaned
    return {}


def _run_analysis_on_transcript(transcript: list[Any], speaker_map: dict[str, str] | None = None) -> dict[str, Any]:
    try:
        from communications.components.ai import ai_analysis
    except Exception as exc:
        raise RuntimeError(f"AI dependencies are unavailable: {exc}") from exc

    try:
        analysis_raw = ai_analysis(transcript, speaker_map=speaker_map or {})
    except Exception as exc:
        raise RuntimeError(f"AI analysis failed: {exc}") from exc

    if isinstance(analysis_raw, dict):
        return analysis_raw
    if isinstance(analysis_raw, str):
        try:
            return json.loads(analysis_raw)
        except json.JSONDecodeError:
            return {"raw": analysis_raw}

    return {"raw": str(analysis_raw)}


def _coerce_seconds(raw_value: Any) -> float:
    try:
        return float(raw_value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _seconds_to_mmss(seconds: float) -> str:
    total = max(int(seconds), 0)
    minutes = total // 60
    secs = total % 60
    return f"{minutes:02d}:{secs:02d}"


def _download_record_file(record_file_id: str) -> str:
    if not BITRIX_WEBHOOK:
        raise BitrixWebhookError("BITRIX_WEBHOOK is not configured")

    external_link_url = f"{BITRIX_WEBHOOK.rstrip('/')}/disk.file.get"
    link_response = requests.get(external_link_url, params={"id": record_file_id}, timeout=20)
    if not link_response.ok:
        raise BitrixWebhookError(f"Failed to get DOWNLOAD_URL: {link_response.text}")

    download_url = link_response.json().get("result", {}).get("DOWNLOAD_URL")
    if not download_url:
        raise BitrixWebhookError("Bitrix response does not contain DOWNLOAD_URL")

    audio_response = requests.get(download_url, stream=True, timeout=60)
    if not audio_response.ok:
        raise BitrixWebhookError(f"Failed to download audio: {audio_response.text}")

    uploads_path = Path(settings.MEDIA_ROOT) / "uploads"
    uploads_path.mkdir(parents=True, exist_ok=True)

    file_path = uploads_path / f"call_{record_file_id}.mp3"
    with file_path.open("wb") as file_obj:
        for chunk in audio_response.iter_content(chunk_size=8192):
            if chunk:
                file_obj.write(chunk)

    return str(file_path)


def _download_record_file_by_url(call_record_url: str, file_seed: str) -> str:
    audio_response = requests.get(call_record_url, stream=True, timeout=60)
    if not audio_response.ok:
        raise BitrixWebhookError(f"Failed to download audio by URL: {audio_response.text}")

    uploads_path = Path(settings.MEDIA_ROOT) / "uploads"
    uploads_path.mkdir(parents=True, exist_ok=True)

    # Пытаемся сохранить расширение из URL, иначе используем .mp3
    path_from_url = urlparse(call_record_url).path or ""
    suffix = Path(path_from_url).suffix or ".mp3"
    safe_seed = str(file_seed).replace("/", "_")
    file_path = uploads_path / f"call_{safe_seed}{suffix}"

    with file_path.open("wb") as file_obj:
        for chunk in audio_response.iter_content(chunk_size=8192):
            if chunk:
                file_obj.write(chunk)

    return str(file_path)


def _run_transcription(audio_file_path: str) -> list[Any]:
    try:
        from communications.components.ai import transcribe
    except Exception as exc:
        raise RuntimeError(f"Transcription dependencies are unavailable: {exc}") from exc

    try:
        return transcribe(audio_file_path)
    except Exception as exc:
        raise RuntimeError(f"Transcription failed: {exc}") from exc


def _nested_get(payload: dict[str, Any], *keys: str) -> Any:
    cursor: Any = payload
    for key in keys:
        if not isinstance(cursor, dict):
            return None
        cursor = cursor.get(key)
    return cursor


def _payload_value(payload: dict[str, Any], field_name: str) -> Any:
    """
    Универсальное чтение поля из разных форматов Bitrix webhook:
    1) JSON: {"data": {"FIELDS": {"CALL_ID": "..."} } }
    2) JSON: {"FIELDS": {"CALL_ID": "..."}}
    3) form-urlencoded: data[CALL_ID]=...
    4) form-urlencoded: data[FIELDS][CALL_ID]=...
    5) плоский формат: CALL_ID=...
    """
    candidates = [
        payload.get(field_name),
        payload.get(field_name.lower()),
        _nested_get(payload, "data", field_name),
        _nested_get(payload, "data", "FIELDS", field_name),
        _nested_get(payload, "FIELDS", field_name),
        payload.get(f"data[{field_name}]"),
        payload.get(f"data[FIELDS][{field_name}]"),
        payload.get(f"FIELDS[{field_name}]"),
    ]
    for value in candidates:
        if value not in (None, ""):
            return value
    return None


def _extract_call_duration_seconds(payload: dict[str, Any]) -> int:
    raw_value = _payload_value(payload, "CALL_DURATION")
    try:
        return int(str(raw_value or "0"))
    except ValueError:
        return 0


def _build_dedupe_key(payload: dict[str, Any], event_name: str, call_id: str) -> str:
    if call_id:
        return f"{event_name.upper()}:{call_id}"

    fallback = (
        payload.get("event_handler_id")
        or payload.get("ts")
        or _payload_value(payload, "event_handler_id")
        or _payload_value(payload, "ts")
    )
    if fallback:
        return f"{event_name.upper()}:{fallback}"
    return ""


def _should_process_payload(payload: dict[str, Any], event_name: str, lead_id: str) -> tuple[bool, str]:
    if "onvoximplantcallend" not in event_name.lower():
        return False, "event is not ONVOXIMPLANTCALLEND"

    duration_seconds = _extract_call_duration_seconds(payload)
    if duration_seconds < MIN_CALL_DURATION_SECONDS:
        return False, f"call duration is less than {MIN_CALL_DURATION_SECONDS} seconds"

    if not lead_id:
        activity_id = _payload_value(payload, "CRM_ACTIVITY_ID")
        call_id = _extract_call_id(payload)
        if not activity_id and not call_id:
            return False, "lead, CRM_ACTIVITY_ID and CALL_ID are absent"

    return True, ""


def _is_failed_call_code(value: Any) -> bool:
    code = str(value or "").strip()
    # Для Bitrix значение "200" обычно означает корректно завершенный вызов.
    if not code or code in {"0", "200"}:
        return False
    return True


def _level_to_logging(level: str) -> int:
    if level == CallProcessingLog.Level.ERROR:
        return logging.ERROR
    if level == CallProcessingLog.Level.WARNING:
        return logging.WARNING
    return logging.INFO


def _archive_processed_event(event: CallWebhookEvent) -> None:
    """
    Копируем только успешно завершенные кейсы в archive DB.
    Это дает "чистую" выборку для последующей аналитики без шумовых webhook-событий.
    """
    archive_alias = getattr(settings, "COMMUNICATIONS_ARCHIVE_DB_ALIAS", "archive")
    try:
        ProcessedCallArchive.objects.using(archive_alias).create(
            source_event_id=event.id,
            call_id=event.call_id,
            lead_id=event.lead_id,
            deal_id=event.deal_id,
            contact_id=event.contact_id,
            record_file_id=event.record_file_id,
            audio_file_path=event.audio_file_path,
            transcript=event.transcript or [],
            analysis=event.analysis or {},
            source_payload=event.raw_payload or {},
        )
        _log(
            event,
            CallProcessingLog.Level.INFO,
            "Archived processed call",
            {"archive_db_alias": archive_alias},
        )
    except Exception as exc:
        _log(
            event,
            CallProcessingLog.Level.WARNING,
            "Archive write failed",
            {"error": str(exc), "error_type": type(exc).__name__},
        )


def _stat_value(stat: dict[str, Any], key: str) -> Any:
    if not isinstance(stat, dict):
        return None
    return stat.get(key) or stat.get(key.lower())


def _stat_log_details(stat: dict[str, Any]) -> dict[str, Any]:
    return {
        "crm_entity_type": _stat_value(stat, "CRM_ENTITY_TYPE"),
        "crm_entity_id": _stat_value(stat, "CRM_ENTITY_ID"),
        "crm_activity_id": _stat_value(stat, "CRM_ACTIVITY_ID"),
        "crm_lead_id": _stat_value(stat, "CRM_LEAD_ID"),
        "crm_contact_id": _stat_value(stat, "CRM_CONTACT_ID"),
        "phone_number": _stat_value(stat, "PHONE_NUMBER"),
        "portal_user_id": _stat_value(stat, "PORTAL_USER_ID"),
        "portal_number": _stat_value(stat, "PORTAL_NUMBER"),
        "call_type": _stat_value(stat, "CALL_TYPE"),
        "call_duration": _stat_value(stat, "CALL_DURATION"),
        "call_failed_code": _stat_value(stat, "CALL_FAILED_CODE"),
        "record_file_id": _stat_value(stat, "RECORD_FILE_ID"),
        "call_record_url": _stat_value(stat, "CALL_RECORD_URL"),
        "has_call_record_url": bool(_stat_value(stat, "CALL_RECORD_URL")),
    }


def _webhook_log_details(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "phone_number": _payload_value(payload, "PHONE_NUMBER"),
        "portal_user_id": _payload_value(payload, "PORTAL_USER_ID"),
        "portal_number": _payload_value(payload, "PORTAL_NUMBER"),
        "call_type": _payload_value(payload, "CALL_TYPE"),
        "call_duration": _payload_value(payload, "CALL_DURATION"),
        "call_failed_code": _payload_value(payload, "CALL_FAILED_CODE"),
    }
