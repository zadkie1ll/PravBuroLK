import json
import logging

from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import LeadMonitor, LeadMonitorStatus
from bitrix.views import get_deal_data_from_bitrix
from .bitrix_api import BitrixAPIError, create_bitrix_task

logger = logging.getLogger(__name__)

BITRIX_WEBHOOK_URL = "https://prav-buro.bitrix24.ru/rest/24/pa1x5irnfpbcnh27/"
BITRIX_FIELD_MODERATOR_ID = "UF_CRM_1774359191"
BITRIX_FIELD_TASK_DESCRIPTION = "UF_CRM_1758727134167"
BITRIX_FIELD_DISABLE_LOGIC = "UF_CRM_1774361781838"

def safe_int(value):
    try:
        if value in (None, "", False):
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


@csrf_exempt
@require_POST
def deal_webhook_handler(request):
    """
    Логика хендлера:
    1. Получаем deal_data
    2. Создаем/обновляем запись LeadMonitor
    3. Если первая задача еще не создана -> создаем ее в Bitrix
    4. Сохраняем task_id в БД
    """

    post_data = request.POST.dict()

    if not post_data and request.body:
        try:
            post_data = json.loads(request.body.decode("utf-8"))
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON body"}, status=400)

    # --- Получаем данные сделки ---
    deal_data, error = get_deal_data_from_bitrix(post_data)
    if error:
        return JsonResponse({"error": error, "payload_keys": list(post_data.keys())}, status=400)
    if not deal_data:
        return JsonResponse({"error": "Empty deal data"}, status=400)

    deal_id = safe_int(deal_data.get("ID"))
    if not deal_id:
        return JsonResponse({"error": "Deal ID not found in deal_data"}, status=400)

    stage_id = (deal_data.get("STAGE_ID") or "").strip()
    responsible_id = safe_int(deal_data.get("ASSIGNED_BY_ID"))
    moderator_id = safe_int(deal_data.get(BITRIX_FIELD_MODERATOR_ID))
    task_description = (deal_data.get(BITRIX_FIELD_TASK_DESCRIPTION) or "").strip()

    if not responsible_id:
        return JsonResponse({"error": "ASSIGNED_BY_ID not found in deal_data"}, status=400)

    try:
        with transaction.atomic():
            monitor, created = LeadMonitor.objects.get_or_create(
                bitrix_deal_id=deal_id,
                defaults={
                    "moderator_bitrix_user_id": moderator_id,
                    "responsible_bitrix_user_id": responsible_id,
                    "task_description": task_description,
                    "entered_logic_at": timezone.now(),
                    "current_stage_id": stage_id,
                    "is_active": True,
                    "status": LeadMonitorStatus.NEW,
                    "raw_deal_data": deal_data,
                }
            )

            if not created:
                monitor.moderator_bitrix_user_id = moderator_id
                monitor.responsible_bitrix_user_id = responsible_id
                monitor.task_description = task_description
                monitor.current_stage_id = stage_id
                monitor.raw_deal_data = deal_data

                if not monitor.entered_logic_at:
                    monitor.entered_logic_at = timezone.now()

                monitor.save()

        # Первую задачу ставим всегда, но только один раз на запись мониторинга
        if not monitor.initial_task_created:
            task_title = f"Прозвонить клиента по сделке #{deal_id}"

            task_id = create_bitrix_task(
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
            monitor.attempts_last_reset_date = timezone.localdate()
            monitor.status = LeadMonitorStatus.ACTIVE
            monitor.status_comment = ""
            monitor.save(
                update_fields=[
                    "initial_bitrix_task_id",
                    "bitrix_task_id",
                    "initial_task_created",
                    "attempts_total",
                    "attempts_today",
                    "attempts_last_reset_date",
                    "status",
                    "status_comment",
                    "updated_at",
                ]
            )

        logger.info(
            "Lead registered successfully: deal_id=%s, current_task_id=%s",
            monitor.bitrix_deal_id,
            monitor.bitrix_task_id,
        )

        return JsonResponse({
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

        LeadMonitor.objects.filter(bitrix_deal_id=deal_id).update(
            status=LeadMonitorStatus.ERROR,
            status_comment=f"Ошибка создания первой задачи: {exc}",
        )

        return JsonResponse(
            {
                "error": "Bitrix task creation failed",
                "details": str(exc),
                "deal_id": deal_id,
            },
            status=500
        )

    except Exception as exc:
        logger.exception("Error while registering deal_id=%s", deal_id)
        return JsonResponse(
            {"error": "Internal server error", "details": str(exc)},
            status=500
        )
    
    #TODO handler for VIKATASTKS