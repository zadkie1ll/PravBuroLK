import json
import logging

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from django.conf import settings
from communications.models import CallWebhookEvent
from communications.services.call_queue import (
    enqueue_call_webhook,
    spawn_background_processing,
    process_call_event
)

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def bitrix_call_webhook(request):
    try:
        payload = _extract_payload(request)

        # 1) Фиксируем входящее событие в локальной БД.
        event, queued = enqueue_call_webhook(payload)
        # 2) Ставим в Celery только события, прошедшие дедупликацию и бизнес-фильтры.
        if queued:
            spawn_background_processing(event.id)

        return JsonResponse(
            {
                "success": True,
                "event_id": event.id,
                "status": event.status,
                "queued": queued,
            },
            status=202,
        )
    except Exception as exc:
        logger.exception("bitrix_call_webhook failed")
        return JsonResponse(
            {
                "success": False,
                "error": "webhook_processing_failed",
                "details": str(exc),
            },
            status=200,
        )


@require_GET
def download_call_to_server(request):
    record_file_id = request.GET.get("record_file_id")
    if not record_file_id:
        return JsonResponse({"error": "record_file_id is required"}, status=400)

    try:
        event = CallWebhookEvent.objects.create(
            event_name="manual_download",
            record_file_id=str(record_file_id),
            raw_payload={"record_file_id": record_file_id, "source": "manual"},
        )
        # Ручной эндпоинт для отладки: тоже отправляем в очередь, как и обычный вебхук.
        spawn_background_processing(event.id)

        return JsonResponse(
            {
                "success": True,
                "event_id": event.id,
                "status": event.status,
            },
            status=202,
        )
    except Exception as exc:
        logger.exception("download_call_to_server failed")
        return JsonResponse(
            {
                "success": False,
                "error": "manual_download_failed",
                "details": str(exc),
            },
            status=500,
        )


def _extract_payload(request):
    if request.content_type and "application/json" in request.content_type:
        try:
            body = request.body.decode("utf-8") if request.body else "{}"
            return json.loads(body)
        except json.JSONDecodeError:
            return {}

    if request.POST:
        return request.POST.dict()

    return {}
@csrf_exempt
@require_POST
def manual_analyze_last_call(request):
    try:
        # ── Unified payload extraction ──────────────────────────────────────
        content_type = (request.content_type or '').lower()

        if 'application/json' in content_type:
            try:
                data = json.loads(request.body.decode('utf-8') if request.body else '{}')
            except json.JSONDecodeError:
                return JsonResponse({"error": "Invalid JSON body"}, status=400)
        else:
            # form-urlencoded (Bitrix default) or multipart/form-data
            data = request.POST.dict()

        # ── Now safely extract parameters ───────────────────────────────────
        entity_type = str(data.get("entity_type", "")).strip().lower()
        entity_id   = str(data.get("entity_id", "")).strip()
        force       = data.get("force", False)  # works for bool in dict

        if not entity_type or not entity_id:
            # For Bitrix webhook case — try to auto-detect from document_id[]
            document_id_parts = [
                data.get(f"document_id[{i}]") 
                for i in range(10)  # safety limit
                if f"document_id[{i}]" in data
            ]

            if len(document_id_parts) >= 3 and document_id_parts[0] == "crm":
                crm_type = document_id_parts[1]  # e.g. CCrmDocumentContact
                raw_id   = document_id_parts[2]  # e.g. CONTACT_13210

                if crm_type == "CCrmDocumentContact":
                    entity_type = "contact"
                    entity_id   = raw_id.replace("CONTACT_", "")
                elif crm_type == "CCrmDocumentDeal":
                    entity_type = "deal"
                    entity_id   = raw_id.replace("DEAL_", "")
                elif crm_type == "CCrmDocumentLead":
                    entity_type = "lead"
                    entity_id   = raw_id.replace("LEAD_", "")
                # add other types if needed

        if not entity_type or not entity_id:
            return JsonResponse({"error": "entity_type и entity_id обязательны (или document_id[] из Bitrix)"}, status=400)

        if entity_type not in ("lead", "deal", "contact"):
            return JsonResponse({"error": "entity_type должен быть lead/deal/contact"}, status=400)
        # Ищем самый свежий подходящий обработанный звонок
        filters = {
            "status": CallWebhookEvent.Status.DONE,
            "audio_file_path__isnull": False,
        }

        if entity_type == "lead":
            filters["lead_id"] = entity_id
        elif entity_type == "deal":
            filters["deal_id"] = entity_id
        elif entity_type == "contact":
            filters["contact_id"] = entity_id

        # Можно также искать в архиве, если основной источник уже почистили
        # event = ProcessedCallArchive.objects.using("archive").filter(**filters).order_by("-created_at").first()

        event = (
            CallWebhookEvent.objects
            .filter(**filters)
            .order_by("-created_at", "-id")
            .first()
        )

        if not event:
            # Можно попробовать найти просто по CRM_ACTIVITY_ID или другим полям,
            # но это уже сложнее — пока оставим базовый вариант
            return JsonResponse({
                "error": f"Не найден завершённый звонок для {entity_type} #{entity_id}"
            }, status=404)

        if not force and event.analysis and isinstance(event.analysis, dict) and event.analysis.get("summary"):
            return JsonResponse({
                "status": "already_analyzed",
                "event_id": event.id,
                "call_id": event.call_id,
                "analyzed_at": event.updated_at.isoformat(),
                "summary": event.analysis.get("summary", "—")
            })

        # Запускаем обработку заново
        if getattr(settings, "COMMUNICATIONS_USE_CELERY", False):
            from communications.tasks import process_call_event_task
            process_call_event_task.delay(event.id)
            status_msg = "Задача на переанализ поставлена в очередь (Celery)"
        else:
            process_call_event(event.id)           # синхронно
            status_msg = "Анализ выполнен синхронно"

        return JsonResponse({
            "status": "ok",
            "event_id": event.id,
            "call_id": event.call_id,
            "message": status_msg,
            "lead_id": event.lead_id,
            "deal_id": event.deal_id,
            "contact_id": event.contact_id,
        })

    except Exception as exc:
        logger.exception("Ошибка при ручном запуске анализа")
        return JsonResponse({"error": str(exc)}, status=500)