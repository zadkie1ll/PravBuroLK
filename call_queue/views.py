from functools import wraps
import json
from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings

from leadreport.models import SalesManager

from .forms import CallResultForm, CallSessionCreateForm, MegafonPhoneListForm, MegafonTestCallForm
from .models import BitrixSyncLog, CallQueueItem, CallSession, CallSessionStatus
from .selectors import get_active_item_for_manager, get_recent_sessions, get_session_with_stats
from .services.telephony.megafon import MegafonAPIError, MegafonTelephonyService
from .services.queue_service import QueueService


MEGAFON_FINAL_STATUS_LABELS = {
    "Success": ("success", "Успешный звонок"),
    "Busy": ("unreachable", "Не дозвонились: занято"),
    "NotAvailable": ("unreachable", "Не дозвонились: недоступен"),
    "missed": ("unreachable", "Не дозвонились: не взял трубку"),
}
MEGAFON_TEST_PHONE_LIST_SESSION_KEY = "megafon_test_phone_list"
MEGAFON_TEST_PHONE_INDEX_SESSION_KEY = "megafon_test_phone_index"
MEGAFON_TEST_CALL_CONFIG_SESSION_KEY = "megafon_test_call_config"
MEGAFON_TEST_ACTIVE_CALL_ID_SESSION_KEY = "megafon_test_active_call_id"
MEGAFON_TEST_LAST_COMPLETED_CALL_ID_SESSION_KEY = "megafon_test_last_completed_call_id"


def append_megafon_log(event_type: str, payload: dict):
    log_path = Path(getattr(settings, "MEGAFON_WEBHOOK_LOG_FILE", ""))
    if not log_path:
        return
    log_path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "event_type": event_type,
        "timestamp": __import__("django.utils.timezone").utils.timezone.now().isoformat(),
        "payload": payload,
    }
    with log_path.open("a", encoding="utf-8") as log_file:
        log_file.write(json.dumps(record, ensure_ascii=False) + "\n")


def extract_megafon_call_id(payload: dict) -> str:
    return str(
        payload.get("callid")
        or payload.get("call_id")
        or payload.get("callId")
        or payload.get("id")
        or ""
    )


def normalize_megafon_payload(request) -> dict:
    if request.POST:
        return request.POST.dict()
    try:
        parsed = json.loads(request.body.decode("utf-8") or "{}") if request.body else {}
    except json.JSONDecodeError:
        parsed = {"raw_body": request.body.decode("utf-8", errors="ignore")}
    if isinstance(parsed, dict):
        return parsed
    return {"payload": parsed}


def serialize_megafon_log(log: BitrixSyncLog) -> dict:
    payload = log.request_payload.get("payload", {}) if isinstance(log.request_payload, dict) else {}
    cmd = payload.get("cmd", "")
    event_type = payload.get("type", "")
    status = payload.get("status", "")
    direction = payload.get("direction", "")
    if cmd == "history":
        title = f"history: {status or 'unknown'}"
    elif cmd == "event":
        title = f"event: {event_type or 'unknown'}"
    elif cmd:
        title = f"{cmd}: {event_type or status or 'received'}"
    else:
        title = "callback"
    return {
        "created_at": timezone.localtime(log.created_at).isoformat(),
        "title": title,
        "cmd": cmd,
        "type": event_type,
        "status": status,
        "direction": direction,
        "payload": payload,
    }


def build_megafon_call_snapshot(call_id: str) -> dict:
    logs = list(
        BitrixSyncLog.objects.filter(entity_type="megafon_webhook", entity_id=call_id, success=True)
        .order_by("created_at", "id")
    )
    timeline = [serialize_megafon_log(log) for log in logs]

    marker = {"state": "pending", "label": "Ожидаем события от МегаФона"}
    manager_answered = False
    latest_history_status = ""

    for entry in timeline:
        if entry["cmd"] == "event" and entry["type"] == "ACCEPTED":
            manager_answered = True
        if entry["cmd"] == "history" and entry["status"]:
            latest_history_status = entry["status"]

    if latest_history_status:
        state, label = MEGAFON_FINAL_STATUS_LABELS.get(
            latest_history_status,
            ("completed", f"Звонок завершен: {latest_history_status}"),
        )
        marker = {"state": state, "label": label}
    elif manager_answered:
        marker = {"state": "in_progress", "label": "Есть ответ по одной из ног звонка"}
    elif timeline:
        marker = {"state": "in_progress", "label": "Звонок в процессе"}

    return {
        "call_id": call_id,
        "marker": marker,
        "manager_answered": manager_answered,
        "latest_history_status": latest_history_status,
        "timeline": timeline[-20:],
    }


def get_megafon_test_phone_list(request) -> list[str]:
    value = request.session.get(MEGAFON_TEST_PHONE_LIST_SESSION_KEY, [])
    return value if isinstance(value, list) else []


def get_megafon_test_phone_index(request, phone_list: list[str]) -> int:
    raw_index = request.session.get(MEGAFON_TEST_PHONE_INDEX_SESSION_KEY, 0)
    if not isinstance(raw_index, int):
        raw_index = 0
    if not phone_list:
        return 0
    return max(0, min(raw_index, len(phone_list) - 1))


def get_megafon_test_call_config(request) -> dict:
    value = request.session.get(MEGAFON_TEST_CALL_CONFIG_SESSION_KEY, {})
    return value if isinstance(value, dict) else {}


def build_megafon_test_call_url(call_id: str, auto_dial: bool = False) -> str:
    url = f"{reverse('call_queue:megafon_test_call')}?callid={call_id}"
    if auto_dial:
        url = f"{url}&autodial=1"
    return url


def start_megafon_test_call(
    request,
    *,
    sales_manager: SalesManager,
    phone: str,
    clid: str,
    show_phone: bool,
) -> tuple[str, dict]:
    telephony_service = MegafonTelephonyService()
    response = telephony_service.make_call(
        phone=phone,
        user=sales_manager.megafon_user or None,
        group=sales_manager.megafon_group or None,
        clid=clid or sales_manager.megafon_clid or None,
        show_phone=show_phone,
    )
    call_id = str(response.get("callid") or "")
    request.session[MEGAFON_TEST_CALL_CONFIG_SESSION_KEY] = {
        "sales_manager_id": sales_manager.pk,
        "clid": clid or "",
        "show_phone": bool(show_phone),
    }
    request.session[MEGAFON_TEST_ACTIVE_CALL_ID_SESSION_KEY] = call_id
    request.session.modified = True
    append_megafon_log(
        "manual_test_call",
        {
            "phone": phone,
            "sales_manager_id": sales_manager.pk,
            "sales_manager_name": sales_manager.name,
            "megafon_user": sales_manager.megafon_user,
            "megafon_group": sales_manager.megafon_group,
            "clid": clid or sales_manager.megafon_clid or "",
            "response": response,
        },
    )
    return call_id, response


def sales_manager_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return login_required(view_func)(request, *args, **kwargs)

        try:
            request.sales_manager_profile = request.user.sales_manager_profile
        except SalesManager.DoesNotExist as exc:
            raise PermissionDenied("Модуль обзвона доступен только менеджерам отдела продаж.") from exc

        if not request.sales_manager_profile.is_active:
            raise PermissionDenied("Ваш профиль менеджера продаж отключен.")

        return view_func(request, *args, **kwargs)

    return _wrapped_view


@login_required
@sales_manager_required
@require_http_methods(["GET", "POST"])
def call_queue_dashboard(request):
    service = QueueService()

    if request.method == "POST":
        form = CallSessionCreateForm(request.POST, bitrix_service=service.deal_service)
        action = request.POST.get("action", "create")
        if form.is_valid():
            session = service.create_session_with_queue(
                manager=request.user,
                filters=form.cleaned_data,
                activate=action == "start",
            )
            messages.success(
                request,
                f"Очередь сформирована: {session.total_items} элементов в сессии #{session.pk}.",
            )
            if action == "start":
                return redirect(f"{session.get_absolute_url()}?auto_next=1")
            return redirect("call_queue:session_detail", session_id=session.pk)
    else:
        form = CallSessionCreateForm(bitrix_service=service.deal_service)

    return render(
        request,
        "call_queue/dashboard.html",
        {
            "form": form,
            "recent_sessions": get_recent_sessions(),
            "sales_manager_profile": request.sales_manager_profile,
        },
    )


@login_required
@sales_manager_required
@require_http_methods(["GET", "POST"])
def megafon_test_call(request):
    phone_list = get_megafon_test_phone_list(request)
    phone_index = get_megafon_test_phone_index(request, phone_list)
    current_phone = phone_list[phone_index] if phone_list else ""
    initial_manager = getattr(request, "sales_manager_profile", None)
    call_config = get_megafon_test_call_config(request)
    initial_sales_manager_id = call_config.get("sales_manager_id") or (initial_manager.pk if initial_manager else None)
    initial_clid = call_config.get("clid", "")
    initial_show_phone = call_config.get("show_phone", True)

    if request.method == "POST":
        action = request.POST.get("action", "start_call")

        if action == "save_phone_list":
            list_form = MegafonPhoneListForm(request.POST)
            form = MegafonTestCallForm(
                initial={
                    "sales_manager": initial_sales_manager_id,
                    "clid": initial_clid,
                    "show_phone": initial_show_phone,
                }
            )
            if list_form.is_valid():
                phone_list = list_form.cleaned_data["phone_list"]
                request.session[MEGAFON_TEST_PHONE_LIST_SESSION_KEY] = phone_list
                request.session[MEGAFON_TEST_PHONE_INDEX_SESSION_KEY] = 0
                phone_index = 0
                messages.success(request, f"Список сохранён: {len(phone_list)} номеров." if phone_list else "Список очищен.")
        elif action == "pick_phone":
            try:
                phone_index = int(request.POST.get("phone_index", "0"))
            except ValueError:
                phone_index = 0
            request.session[MEGAFON_TEST_PHONE_INDEX_SESSION_KEY] = phone_index
            return redirect("call_queue:megafon_test_call")
        else:
            form = MegafonTestCallForm(request.POST)
            list_form = MegafonPhoneListForm(initial={"phone_list": "\n".join(phone_list)})
            if form.is_valid():
                if not current_phone:
                    messages.error(request, "Сначала сохраните список номеров и выберите текущий номер.")
                    current_phone = phone_list[phone_index] if phone_list else ""
                else:
                    sales_manager = form.cleaned_data["sales_manager"]
                    try:
                        call_id, _response = start_megafon_test_call(
                            request,
                            phone=current_phone,
                            sales_manager=sales_manager,
                            clid=form.cleaned_data["clid"] or sales_manager.megafon_clid or None,
                            show_phone=bool(form.cleaned_data.get("show_phone")),
                        )
                    except MegafonAPIError as exc:
                        messages.error(request, f"Не удалось запустить тестовый звонок: {exc}")
                    except Exception as exc:
                        messages.error(request, f"Ошибка при запросе в МегаФон АТС: {exc}")
                    else:
                        auto_dial = request.POST.get("auto_dial") == "on"
                        messages.success(
                            request,
                            f"Тестовый звонок запущен для номера {current_phone}. Call ID: {call_id}.",
                        )
                        return redirect(build_megafon_test_call_url(call_id, auto_dial=auto_dial))
    else:
        form = MegafonTestCallForm(
            initial={
                "sales_manager": initial_sales_manager_id,
                "clid": initial_clid,
                "show_phone": initial_show_phone,
            }
        )
        list_form = MegafonPhoneListForm(initial={"phone_list": "\n".join(phone_list)})

    if request.method == "POST" and "form" not in locals():
        form = MegafonTestCallForm(
            initial={
                "sales_manager": initial_sales_manager_id,
                "clid": initial_clid,
                "show_phone": initial_show_phone,
            }
        )
    if request.method == "POST" and "list_form" not in locals():
        list_form = MegafonPhoneListForm(initial={"phone_list": "\n".join(phone_list)})

    current_call_id = request.GET.get("callid", "").strip()
    auto_dial_enabled = request.GET.get("autodial") == "1"
    current_snapshot = build_megafon_call_snapshot(current_call_id) if current_call_id else None
    phone_entries = [
        {"index": idx, "phone": phone, "is_current": idx == phone_index}
        for idx, phone in enumerate(phone_list)
    ]

    return render(
        request,
        "call_queue/megafon_test_call.html",
        {
            "form": form,
            "list_form": list_form,
            "sales_manager_profile": request.sales_manager_profile,
            "megafon_webhook_url": getattr(settings, "SITE_BASE_URL", "").rstrip("/") + "/call-queue/megafon/webhook/",
            "megafon_log_file": getattr(settings, "MEGAFON_WEBHOOK_LOG_FILE", ""),
            "current_call_id": current_call_id,
            "current_snapshot": current_snapshot,
            "phone_entries": phone_entries,
            "current_phone": current_phone,
            "auto_dial_enabled": auto_dial_enabled,
        },
    )


@login_required
@sales_manager_required
@require_http_methods(["GET"])
def megafon_call_status(request):
    call_id = request.GET.get("callid", "").strip()
    if not call_id:
        return JsonResponse({"ok": False, "error": "callid is required"}, status=400)
    return JsonResponse({"ok": True, "snapshot": build_megafon_call_snapshot(call_id)})


@login_required
@sales_manager_required
@require_http_methods(["POST"])
def megafon_auto_next_call(request):
    completed_call_id = request.POST.get("completed_callid", "").strip()
    if not completed_call_id:
        return JsonResponse({"ok": False, "error": "completed_callid is required"}, status=400)

    snapshot = build_megafon_call_snapshot(completed_call_id)
    if not snapshot["latest_history_status"]:
        return JsonResponse({"ok": False, "error": "call is not completed yet"}, status=409)

    active_call_id = str(request.session.get(MEGAFON_TEST_ACTIVE_CALL_ID_SESSION_KEY, "") or "")
    if request.session.get(MEGAFON_TEST_LAST_COMPLETED_CALL_ID_SESSION_KEY) == completed_call_id:
        return JsonResponse(
            {
                "ok": True,
                "started": False,
                "already_processed": True,
                "active_call_id": active_call_id,
                "redirect_url": build_megafon_test_call_url(active_call_id, auto_dial=True) if active_call_id else "",
            }
        )

    phone_list = get_megafon_test_phone_list(request)
    if not phone_list:
        return JsonResponse({"ok": True, "started": False, "no_next": True})

    current_index = get_megafon_test_phone_index(request, phone_list)
    if current_index >= len(phone_list) - 1:
        request.session[MEGAFON_TEST_LAST_COMPLETED_CALL_ID_SESSION_KEY] = completed_call_id
        request.session.modified = True
        return JsonResponse({"ok": True, "started": False, "no_next": True})

    call_config = get_megafon_test_call_config(request)
    sales_manager = SalesManager.objects.filter(
        pk=call_config.get("sales_manager_id"),
        is_active=True,
    ).first()
    if not sales_manager:
        return JsonResponse({"ok": False, "error": "sales manager config is missing"}, status=400)

    next_index = current_index + 1
    next_phone = phone_list[next_index]

    try:
        next_call_id, _response = start_megafon_test_call(
            request,
            sales_manager=sales_manager,
            phone=next_phone,
            clid=call_config.get("clid", "") or sales_manager.megafon_clid or None,
            show_phone=bool(call_config.get("show_phone", True)),
        )
    except MegafonAPIError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=502)
    except Exception as exc:
        return JsonResponse({"ok": False, "error": f"Ошибка при запросе в МегаФон АТС: {exc}"}, status=500)

    request.session[MEGAFON_TEST_PHONE_INDEX_SESSION_KEY] = next_index
    request.session[MEGAFON_TEST_LAST_COMPLETED_CALL_ID_SESSION_KEY] = completed_call_id
    request.session.modified = True

    return JsonResponse(
        {
            "ok": True,
            "started": True,
            "call_id": next_call_id,
            "phone": next_phone,
            "index": next_index,
            "redirect_url": build_megafon_test_call_url(next_call_id, auto_dial=True),
        }
    )


@login_required
@sales_manager_required
@require_http_methods(["GET", "POST"])
def call_session_detail(request, session_id: int):
    session = get_object_or_404(CallSession, pk=session_id)
    service = QueueService()

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "start_session" and session.status == CallSessionStatus.DRAFT:
            session.status = CallSessionStatus.ACTIVE
            session.save(update_fields=["status", "updated_at"])
            return redirect(f"{session.get_absolute_url()}?auto_next=1")

        if action == "take_next":
            return redirect(f"{session.get_absolute_url()}?auto_next=1")

        if action == "start_call":
            current_item = get_active_item_for_manager(session, request.user)
            if not current_item:
                messages.warning(request, "Сначала возьмите лид в работу.")
                return redirect("call_queue:session_detail", session_id=session.pk)

            telephony_service = MegafonTelephonyService()
            try:
                response = telephony_service.make_call(
                    phone=current_item.phone,
                    user=request.sales_manager_profile.megafon_user or None,
                    group=request.sales_manager_profile.megafon_group or None,
                    clid=request.sales_manager_profile.megafon_clid or None,
                    show_phone=True,
                )
            except MegafonAPIError as exc:
                messages.error(request, f"Не удалось запустить звонок через МегаФон: {exc}")
            except Exception as exc:
                messages.error(request, f"Ошибка при запросе в МегаФон АТС: {exc}")
            else:
                current_item.last_provider_call_id = str(response.get("callid") or "")
                current_item.save(update_fields=["last_provider_call_id", "updated_at"])
                BitrixSyncLog.objects.create(
                    entity_type="megafon_call",
                    entity_id=current_item.last_provider_call_id,
                    action="makecall",
                    request_payload={
                        "phone": current_item.phone,
                        "user": request.sales_manager_profile.megafon_user,
                        "group": request.sales_manager_profile.megafon_group,
                        "clid": request.sales_manager_profile.megafon_clid,
                    },
                    response_payload=response,
                    success=True,
                )
                messages.success(
                    request,
                    f"Звонок запущен через МегаФон. Call ID: {current_item.last_provider_call_id}.",
                )
            return redirect("call_queue:session_detail", session_id=session.pk)

        if action == "complete_session":
            session.status = CallSessionStatus.COMPLETED
            session.save(update_fields=["status", "updated_at"])
            messages.success(request, "Сессия завершена.")
            return redirect("call_queue:session_detail", session_id=session.pk)

        if action == "submit_result":
            result = request.POST.get("result", "")
            form = CallResultForm(request.POST)
            if form.is_valid() and result:
                queue_item = get_object_or_404(
                    CallQueueItem,
                    pk=form.cleaned_data["queue_item_id"],
                    session=session,
                )
                outcome = service.process_call_result(
                    queue_item=queue_item,
                    manager=request.user,
                    result=result,
                    comment=form.cleaned_data["comment"],
                )
                if outcome["sync_error"]:
                    messages.warning(
                        request,
                        "Результат сохранен локально, но синхронизация с Bitrix24 не прошла. "
                        f"Ошибка: {outcome['sync_error']}",
                    )
                else:
                    messages.success(request, "Результат звонка сохранен и отправлен в Bitrix24.")
                return redirect(f"{session.get_absolute_url()}?auto_next=1")

    current_item = get_active_item_for_manager(session, request.user)
    if not current_item and request.GET.get("auto_next") == "1" and session.status != CallSessionStatus.COMPLETED:
        current_item = service.get_next_item_for_manager(session, request.user)
        if current_item:
            messages.info(request, f"Загружен следующий лид: {current_item.client_name or current_item.phone}.")
        else:
            messages.info(request, "Доступных лидов в очереди сейчас нет.")

    session = get_session_with_stats(session.pk)
    attempts = current_item.attempts.select_related("manager").all()[:10] if current_item else []
    result_form = CallResultForm(initial={"queue_item_id": current_item.pk}) if current_item else CallResultForm()

    return render(
        request,
        "call_queue/session_detail.html",
        {
            "session": session,
            "current_item": current_item,
            "attempts": attempts,
            "result_form": result_form,
            "sales_manager_profile": request.sales_manager_profile,
        },
    )


@csrf_exempt
@require_http_methods(["POST"])
def megafon_webhook(request):
    expected_key = getattr(settings, "MEGAFON_VATS_CRM_AUTH_KEY", "")
    received_key = (
        request.headers.get("X-CRM-AUTH")
        or request.headers.get("X-Megafon-Auth")
        or request.POST.get("crm_token")
        or request.POST.get("auth")
        or request.GET.get("auth")
    )
    payload = normalize_megafon_payload(request)
    call_id = extract_megafon_call_id(payload)

    append_megafon_log(
        "incoming_callback_raw",
        {
            "headers": {
                "X-CRM-AUTH": request.headers.get("X-CRM-AUTH", ""),
                "X-Megafon-Auth": request.headers.get("X-Megafon-Auth", ""),
            },
            "query": request.GET.dict(),
            "post": request.POST.dict(),
            "payload": payload,
        },
    )

    if not expected_key or received_key != expected_key:
        BitrixSyncLog.objects.create(
            entity_type="megafon_webhook",
            entity_id=call_id,
            action="incoming_callback_rejected",
            request_payload={
                "headers": {
                    "X-CRM-AUTH": request.headers.get("X-CRM-AUTH", ""),
                    "X-Megafon-Auth": request.headers.get("X-Megafon-Auth", ""),
                },
                "query": request.GET.dict(),
                "post": request.POST.dict(),
                "payload": payload,
            },
            response_payload={"ok": False},
            success=False,
            error_text="Invalid Megafon webhook auth key",
        )
        append_megafon_log(
            "incoming_callback_rejected",
            {
                "reason": "invalid_auth_key",
                "received_key": bool(received_key),
                "payload": payload,
            },
        )
        return HttpResponseForbidden("Invalid auth key")

    BitrixSyncLog.objects.create(
        entity_type="megafon_webhook",
        entity_id=call_id,
        action=f"{payload.get('cmd', 'callback')}:{payload.get('type', payload.get('status', 'received'))}",
        request_payload={
            "headers": {
                "X-CRM-AUTH": request.headers.get("X-CRM-AUTH", ""),
                "X-Megafon-Auth": request.headers.get("X-Megafon-Auth", ""),
            },
            "query": request.GET.dict(),
            "post": request.POST.dict(),
            "payload": payload,
        },
        response_payload={"accepted": True},
        success=True,
    )
    append_megafon_log(
        "incoming_callback_accepted",
        {
            "call_id": call_id,
            "payload": payload,
        },
    )
    return JsonResponse({"ok": True})
