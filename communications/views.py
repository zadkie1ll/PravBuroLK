import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from communications.models import CallWebhookEvent
from communications.services.call_queue import (
    enqueue_call_webhook,
    spawn_background_processing,
)


@csrf_exempt
@require_POST
def bitrix_call_webhook(request):
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


@require_GET
def download_call_to_server(request):
    record_file_id = request.GET.get("record_file_id")
    if not record_file_id:
        return JsonResponse({"error": "record_file_id is required"}, status=400)

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
