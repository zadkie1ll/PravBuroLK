from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from sqlalchemy.orm import Session

from ..config import settings
from ..models import CallProcessingLog, CallStatus, CallWebhookEvent, ProcessedCallArchive
from ..redis_client import acquire_dedupe_lock
from .bitrix_gateway_client import BitrixAPIError, BitrixClient
from . import ai

logger = logging.getLogger(__name__)


class BitrixWebhookError(Exception):
    pass


def enqueue_call_webhook(db: Session, payload: dict[str, Any]) -> tuple[CallWebhookEvent, bool]:
    event_name = _extract_event_name(payload)
    call_id = _extract_call_id(payload)
    lead_id = _extract_lead_id(payload)
    contact_id = _extract_contact_id(payload)
    record_file_id = _extract_record_file_id(payload)
    dedupe_key = _build_dedupe_key(payload, event_name, call_id)

    if dedupe_key:
        existing = (
            db.query(CallWebhookEvent)
            .filter(CallWebhookEvent.dedupe_key == dedupe_key)
            .filter(CallWebhookEvent.status != CallStatus.FAILED.value)
            .order_by(CallWebhookEvent.id.desc())
            .first()
        )
        if existing:
            _log(db, existing, "info", "Duplicate webhook skipped", {"dedupe_key": dedupe_key})
            return existing, False

        # Быстрый предохранитель от гонки при параллельных ретраях того же webhook'а,
        # пока первая запись ещё не закоммитилась в БД.
        if not acquire_dedupe_lock(dedupe_key):
            existing = (
                db.query(CallWebhookEvent)
                .filter(CallWebhookEvent.dedupe_key == dedupe_key)
                .order_by(CallWebhookEvent.id.desc())
                .first()
            )
            if existing:
                return existing, False

    should_process, ignore_reason = _should_process_payload(payload, event_name, lead_id)

    event = CallWebhookEvent(
        event_name=event_name,
        call_id=call_id,
        lead_id=lead_id,
        contact_id=contact_id,
        record_file_id=record_file_id,
        dedupe_key=dedupe_key,
        raw_payload=payload,
        status=CallStatus.PENDING.value if should_process else CallStatus.IGNORED.value,
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    if should_process:
        _log(db, event, "info", "Webhook accepted", _webhook_log_details(payload))
        return event, True

    _log(db, event, "info", "Webhook ignored at ingress", {"reason": ignore_reason, **_webhook_log_details(payload)})
    return event, False


def process_call_event(db: Session, event_id: int, raise_on_error: bool = False) -> None:
    event = db.query(CallWebhookEvent).filter(CallWebhookEvent.id == event_id).first()
    if not event:
        logger.warning("Event %s not found", event_id)
        return

    if event.status in {CallStatus.DONE.value, CallStatus.IGNORED.value}:
        return

    event.status = CallStatus.PROCESSING.value
    event.attempts += 1
    event.error_message = ""
    db.commit()
    _log(db, event, "info", "Processing started")

    try:
        if not _is_call_finished_event(event):
            _finish_ignored(db, event, "Webhook ignored: call is not finished")
            return

        if _is_call_without_recording(event):
            _finish_ignored(
                db,
                event,
                "Webhook ignored: call ended without recording",
                {
                    "call_duration": _payload_value(event.raw_payload, "CALL_DURATION"),
                    "call_failed_code": _payload_value(event.raw_payload, "CALL_FAILED_CODE"),
                },
            )
            return

        duration_seconds = _extract_call_duration_seconds(event.raw_payload)
        if duration_seconds < settings.min_call_duration_seconds:
            _finish_ignored(
                db,
                event,
                "Webhook ignored: call is shorter than the minimum duration",
                {"call_duration": duration_seconds, "min_duration": settings.min_call_duration_seconds},
            )
            return

        if not event.call_id:
            _finish_ignored(db, event, "Webhook ignored: CALL_ID is absent")
            return

        # Жесткая последовательность обработки:
        # 1) берем CALL_ID из webhook
        # 2) запрашиваем voximplant.statistic.get по exact CALL_ID
        # 3) используем CALL_RECORD_URL из статистики для скачивания записи
        stat = _get_call_stat_by_call_id(event.call_id)
        _log(db, event, "info", "Call statistic fetched", _stat_log_details(stat))

        crm_entity_type, crm_entity_id = _extract_crm_entity(event.raw_payload, stat)
        allowed_types = settings.allowed_crm_entity_types_set
        if crm_entity_type and allowed_types and crm_entity_type not in allowed_types:
            _finish_ignored(
                db,
                event,
                "Webhook ignored: CRM entity type is not allowed",
                {
                    "crm_entity_type": crm_entity_type,
                    "crm_entity_id": crm_entity_id,
                    "allowed_types": sorted(allowed_types),
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
            _finish_ignored(db, event, "Webhook ignored: CRM entity is absent", _stat_log_details(stat))
            return

        event.lead_id = str(lead_id or "")
        event.deal_id = str(deal_id or "")
        event.contact_id = str(contact_id or "")
        db.commit()
        _log(
            db,
            event,
            "info",
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
            db.commit()

        if not call_record_url:
            _finish_ignored(
                db,
                event,
                "Webhook ignored: CALL_RECORD_URL is absent in statistic.get",
                {"call_id": event.call_id, **_stat_log_details(stat)},
                level="warning",
            )
            return

        audio_file_path = _download_record_file_by_url(call_record_url, event.call_id)
        event.audio_file_path = audio_file_path
        db.commit()
        _log(db, event, "info", "Call recording downloaded", {"audio_file_path": audio_file_path})

        transcript = ai.transcribe(audio_file_path)
        event.transcript = transcript or []
        db.commit()
        _log(db, event, "info", "Call transcription completed", {"segments": len(transcript or [])})

        speaker_map = _run_diarization(transcript or [])
        if speaker_map:
            _log(db, event, "info", "Call diarization completed", {"speeches": len(speaker_map)})
        else:
            _log(db, event, "warning", "Call diarization returned empty map")

        analysis = _run_analysis(transcript or [], speaker_map=speaker_map)
        if speaker_map:
            analysis["speaker_map"] = speaker_map
        event.analysis = analysis or {}
        event.status = CallStatus.DONE.value
        db.commit()
        _log(db, event, "info", "Call analysis completed")

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
                db,
                event,
                "info",
                "CRM comment posted",
                {"entity_type": comment_entity_type, "entity_id": comment_entity_id, "owner_type_id": owner_type_id},
            )
        else:
            _log(db, event, "warning", "CRM comment skipped: owner/entity is absent")

        _archive_processed_event(db, event)

    except Exception as exc:
        event.status = CallStatus.FAILED.value
        event.error_message = str(exc)
        db.commit()
        _log(db, event, "error", "Processing failed", {"error": str(exc), "error_type": type(exc).__name__})
        if raise_on_error:
            raise


def _finish_ignored(
    db: Session, event: CallWebhookEvent, message: str, details: dict[str, Any] | None = None, level: str = "info"
) -> None:
    event.status = CallStatus.IGNORED.value
    db.commit()
    _log(db, event, level, message, details)


def process_pending_queue(db: Session, limit: int = 50) -> int:
    pending = (
        db.query(CallWebhookEvent)
        .filter(CallWebhookEvent.status == CallStatus.PENDING.value)
        .order_by(CallWebhookEvent.created_at)
        .limit(limit)
        .all()
    )
    for event in pending:
        process_call_event(db, event.id)
    return len(pending)


def _log(db: Session, event: CallWebhookEvent, level: str, message: str, details: dict[str, Any] | None = None) -> None:
    db.add(CallProcessingLog(event_id=event.id, level=level, message=message, details=details or {}))
    db.commit()
    logger.log(_level_to_logging(level), "event_id=%s %s %s", event.id, message, details or {})


def _level_to_logging(level: str) -> int:
    if level == "error":
        return logging.ERROR
    if level == "warning":
        return logging.WARNING
    return logging.INFO


def _extract_event_name(payload: dict[str, Any]) -> str:
    return str(payload.get("event") or payload.get("EVENT") or payload.get("EVENT_NAME") or payload.get("type") or "")


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
    if str(owner_type_id or "") == settings.bitrix_lead_owner_type_id and owner_id:
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
    if str(owner_type_id or "") == settings.bitrix_contact_owner_type_id and owner_id:
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
    return str(lead_id) if lead_id else ""


def _extract_contact_id_from_stat(stat: dict[str, Any]) -> str:
    entity_type = str(_stat_value(stat, "CRM_ENTITY_TYPE") or "").upper()
    entity_id = _stat_value(stat, "CRM_ENTITY_ID")
    if entity_type == "CONTACT" and entity_id:
        return str(entity_id)
    contact_id = _stat_value(stat, "CRM_CONTACT_ID")
    return str(contact_id) if contact_id else ""


def _extract_crm_entity(payload: dict[str, Any], stat: dict[str, Any]) -> tuple[str, str]:
    payload_type = str(_payload_value(payload, "CRM_ENTITY_TYPE") or _payload_value(payload, "ENTITY_TYPE") or "").upper()
    payload_id = str(_payload_value(payload, "CRM_ENTITY_ID") or _payload_value(payload, "ENTITY_ID") or "")
    if payload_type and payload_id:
        return payload_type, payload_id

    stat_type = str(_stat_value(stat, "CRM_ENTITY_TYPE") or "").upper()
    stat_id = str(_stat_value(stat, "CRM_ENTITY_ID") or "")
    if stat_type and stat_id:
        return stat_type, stat_id

    return "", ""


def _is_call_finished_event(event: CallWebhookEvent) -> bool:
    call_state = _payload_value(event.raw_payload, "CALL_STATE")
    marker_values = [event.event_name.lower(), str(call_state or "").lower()]
    joined = " ".join(value for value in marker_values if value)
    if not joined:
        return True
    finished_markers = ["onvoximplantcallend", "call_end", "finished", "hangup", "end"]
    return any(marker in joined for marker in finished_markers)


def _is_call_without_recording(event: CallWebhookEvent) -> bool:
    duration_raw = _extract_call_duration_seconds(event.raw_payload)
    failed_code = _payload_value(event.raw_payload, "CALL_FAILED_CODE")
    return _is_failed_call_code(failed_code) or duration_raw == 0


def _get_call_stat_by_call_id(call_id: str) -> dict[str, Any]:
    if not call_id:
        return {}
    try:
        result = BitrixClient().call("voximplant.statistic.get", {"filter": {"CALL_ID": call_id}})
    except BitrixAPIError as exc:
        raise BitrixWebhookError(str(exc)) from exc

    if isinstance(result, list) and result:
        exact_with_url = [
            row for row in result
            if isinstance(row, dict) and str(row.get("CALL_ID") or "") == call_id and bool(row.get("CALL_RECORD_URL"))
        ]
        if exact_with_url:
            return exact_with_url[0]

        exact_any = [row for row in result if isinstance(row, dict) and str(row.get("CALL_ID") or "") == call_id]
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

    deadline = time.time() + settings.bitrix_stat_poll_timeout_seconds
    attempts = 0
    while time.time() < deadline:
        attempts += 1
        stat = _get_call_stat_by_call_id(call_id)
        if _stat_value(stat, "CALL_RECORD_URL"):
            return stat
        time.sleep(settings.bitrix_stat_poll_interval_seconds)

    raise BitrixWebhookError(
        "CALL_RECORD_URL is absent in statistic.get after retries "
        f"(timeout={settings.bitrix_stat_poll_timeout_seconds}s, "
        f"interval={settings.bitrix_stat_poll_interval_seconds}s, attempts={attempts})"
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
    mapped = settings.owner_type_to_entity_type.get(str(owner_type_id or "").strip())
    return mapped.lower() if mapped else ""


def _post_call_result_comment(
    entity_type: str, entity_id: str, owner_type_id: str, call_id: str, transcript: list[Any], analysis: dict[str, Any]
) -> None:
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

    fields: dict[str, Any] = {"ENTITY_ID": entity_id, "COMMENT": comment}
    if entity_type:
        fields["ENTITY_TYPE"] = entity_type.lower()
    if owner_type_id:
        fields["ENTITY_TYPE_ID"] = owner_type_id

    try:
        BitrixClient().call("crm.timeline.comment.add", {"fields": fields})
    except BitrixAPIError as exc:
        raise BitrixWebhookError(f"Failed to add timeline comment: {exc}") from exc


def _format_transcript_for_comment(transcript: list[Any], speaker_map: dict[str, Any] | None = None) -> str:
    if not transcript:
        return "Транскрипт отсутствует или пустой."

    normalized_speaker_map = speaker_map if isinstance(speaker_map, dict) else {}
    lines: list[str] = []
    current_speaker = None
    current_block: list[str] = []

    def flush_block():
        if not current_block:
            return
        block_text = " ".join(current_block).strip()
        if len(block_text) > 300:
            block_text = block_text[:280] + "… [длинный фрагмент]"
        prefix = f"[{_format_role_label(current_speaker)}]" if current_speaker else ""
        lines.append(f"{prefix} {block_text}")
        current_block.clear()

    for item in transcript:
        if isinstance(item, dict):
            text = str(item.get("text") or item.get("TEXT") or "").strip()
            start = _coerce_seconds(item.get("start") or item.get("start_seconds"))
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            text = str(item[0] or "").strip()
            start = _coerce_seconds(item[1])
        else:
            text = str(item or "").strip()
            start = 0.0

        if not text:
            continue

        ts = _seconds_to_mmss(start)
        speaker = normalized_speaker_map.get(ts, "unknown")

        if speaker != current_speaker and current_block:
            flush_block()

        current_speaker = speaker
        current_block.append(text)

        if len(" ".join(current_block)) > 450:
            flush_block()

    flush_block()

    if not lines:
        return "Транскрипт пустой после обработки."

    formatted = "\n".join(lines)
    max_chars = settings.bitrix_comment_transcript_max_chars
    if len(formatted) > max_chars:
        formatted = formatted[: max_chars - 30].rstrip() + "\n… (обрезано)"

    return (
        "Транскрипция звонка (с таймкодами и разделением по спикерам):\n"
        "────────────────────────────────────────\n"
        f"{formatted}\n"
        "────────────────────────────────────────"
    )


def _format_summary_for_comment(analysis: dict[str, Any]) -> str:
    if not analysis:
        return "-"
    max_chars = settings.bitrix_comment_analysis_max_chars
    candidates = [analysis.get("summary"), analysis.get("short_summary"), analysis.get("result")]
    for value in candidates:
        text = str(value or "").strip()
        if text:
            return text[:max_chars]

    recommendations = analysis.get("recommendations")
    if isinstance(recommendations, list) and recommendations:
        text = "; ".join(str(item).strip() for item in recommendations if str(item).strip())
        if text:
            return text[:max_chars]
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
    mistakes_text = "; ".join(str(item).strip() for item in mistakes if str(item).strip()) if isinstance(mistakes, list) else ""
    mistakes_text = mistakes_text or "-"

    recommendations = analysis.get("recommendations")
    recommendations_text = (
        "; ".join(str(item).strip() for item in recommendations if str(item).strip())
        if isinstance(recommendations, list)
        else ""
    )
    recommendations_text = recommendations_text or "-"

    lines = [f"Score: {score_text}/5"]
    lines.extend(f"- {label}: {value}" for label, value in checks)
    lines.append(f"- Ошибки: {mistakes_text}")
    lines.append(f"- Рекомендации: {recommendations_text}")
    rendered = "\n".join(lines).strip()
    max_chars = settings.bitrix_comment_analysis_max_chars
    if len(rendered) > max_chars:
        return f"{rendered[:max_chars].rstrip()}\n...[обрезано]"
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


def _run_diarization(transcript: list[Any]) -> dict[str, str]:
    try:
        mapping = ai.diarize_transcript(transcript)
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


def _run_analysis(transcript: list[Any], speaker_map: dict[str, str] | None = None) -> dict[str, Any]:
    try:
        analysis_raw = ai.ai_analysis(transcript, speaker_map=speaker_map or {})
    except Exception as exc:
        raise RuntimeError(f"AI analysis failed: {exc}") from exc

    if isinstance(analysis_raw, dict):
        return analysis_raw
    if isinstance(analysis_raw, str):
        import json

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


def _download_record_file_by_url(call_record_url: str, file_seed: str) -> str:
    audio_response = requests.get(call_record_url, stream=True, timeout=60)
    if not audio_response.ok:
        raise BitrixWebhookError(f"Failed to download audio by URL: {audio_response.text}")

    uploads_path = Path(settings.media_root) / "uploads"
    uploads_path.mkdir(parents=True, exist_ok=True)

    path_from_url = urlparse(call_record_url).path or ""
    suffix = Path(path_from_url).suffix or ".mp3"
    safe_seed = str(file_seed).replace("/", "_")
    file_path = uploads_path / f"call_{safe_seed}{suffix}"

    with file_path.open("wb") as file_obj:
        for chunk in audio_response.iter_content(chunk_size=8192):
            if chunk:
                file_obj.write(chunk)

    return str(file_path)


def _nested_get(payload: dict[str, Any], *keys: str) -> Any:
    cursor: Any = payload
    for key in keys:
        if not isinstance(cursor, dict):
            return None
        cursor = cursor.get(key)
    return cursor


def _payload_value(payload: dict[str, Any], field_name: str) -> Any:
    """Универсальное чтение поля из разных форматов Bitrix webhook (JSON/form-urlencoded/плоский)."""
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
    if duration_seconds < settings.min_call_duration_seconds:
        return False, f"call duration is less than {settings.min_call_duration_seconds} seconds"

    if not lead_id:
        activity_id = _payload_value(payload, "CRM_ACTIVITY_ID")
        call_id = _extract_call_id(payload)
        if not activity_id and not call_id:
            return False, "lead, CRM_ACTIVITY_ID and CALL_ID are absent"

    return True, ""


def _is_failed_call_code(value: Any) -> bool:
    code = str(value or "").strip()
    if not code or code in {"0", "200"}:
        return False
    return True


def _archive_processed_event(db: Session, event: CallWebhookEvent) -> None:
    try:
        db.add(
            ProcessedCallArchive(
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
        )
        db.commit()
        _log(db, event, "info", "Archived processed call")
    except Exception as exc:
        db.rollback()
        _log(db, event, "warning", "Archive write failed", {"error": str(exc), "error_type": type(exc).__name__})


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
        "call_type": _stat_value(stat, "CALL_TYPE"),
        "call_duration": _stat_value(stat, "CALL_DURATION"),
        "call_failed_code": _stat_value(stat, "CALL_FAILED_CODE"),
        "record_file_id": _stat_value(stat, "RECORD_FILE_ID"),
        "has_call_record_url": bool(_stat_value(stat, "CALL_RECORD_URL")),
    }


def _webhook_log_details(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "phone_number": _payload_value(payload, "PHONE_NUMBER"),
        "call_type": _payload_value(payload, "CALL_TYPE"),
        "call_duration": _payload_value(payload, "CALL_DURATION"),
        "call_failed_code": _payload_value(payload, "CALL_FAILED_CODE"),
    }
