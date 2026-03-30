from functools import wraps
import json
from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings

from leadreport.models import SalesManager

from .forms import CallResultForm, CallSessionCreateForm, MegafonTestCallForm
from .models import BitrixSyncLog, CallQueueItem, CallSession, CallSessionStatus
from .selectors import get_active_item_for_manager, get_recent_sessions, get_session_with_stats
from .services.telephony.megafon import MegafonAPIError, MegafonTelephonyService
from .services.queue_service import QueueService


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
    if request.method == "POST":
        form = MegafonTestCallForm(request.POST)
        if form.is_valid():
            sales_manager = form.cleaned_data["sales_manager"]
            telephony_service = MegafonTelephonyService()
            try:
                response = telephony_service.make_call(
                    phone=form.cleaned_data["phone"],
                    user=sales_manager.megafon_user or None,
                    group=sales_manager.megafon_group or None,
                    clid=form.cleaned_data["clid"] or sales_manager.megafon_clid or None,
                    show_phone=bool(form.cleaned_data.get("show_phone")),
                )
            except MegafonAPIError as exc:
                messages.error(request, f"Не удалось запустить тестовый звонок: {exc}")
            except Exception as exc:
                messages.error(request, f"Ошибка при запросе в МегаФон АТС: {exc}")
            else:
                append_megafon_log(
                    "manual_test_call",
                    {
                        "phone": form.cleaned_data["phone"],
                        "sales_manager_id": sales_manager.pk,
                        "sales_manager_name": sales_manager.name,
                        "megafon_user": sales_manager.megafon_user,
                        "megafon_group": sales_manager.megafon_group,
                        "clid": form.cleaned_data["clid"] or sales_manager.megafon_clid or "",
                        "response": response,
                    },
                )
                messages.success(
                    request,
                    f"Тестовый звонок запущен. Call ID: {response.get('callid')}.",
                )
                return redirect("call_queue:megafon_test_call")
    else:
        initial_manager = getattr(request, "sales_manager_profile", None)
        form = MegafonTestCallForm(initial={"sales_manager": initial_manager.pk if initial_manager else None})

    return render(
        request,
        "call_queue/megafon_test_call.html",
        {
            "form": form,
            "sales_manager_profile": request.sales_manager_profile,
            "megafon_webhook_url": getattr(settings, "SITE_BASE_URL", "").rstrip("/") + "/call-queue/megafon/webhook/",
            "megafon_log_file": getattr(settings, "MEGAFON_WEBHOOK_LOG_FILE", ""),
        },
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
        or request.POST.get("auth")
        or request.GET.get("auth")
    )

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}") if request.body else {}
    except json.JSONDecodeError:
        payload = {"raw_body": request.body.decode("utf-8", errors="ignore")}

    if not isinstance(payload, dict):
        payload = {"payload": payload}

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
            entity_id=str(payload.get("call_id") or payload.get("id") or ""),
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
        entity_id=str(payload.get("call_id") or payload.get("id") or ""),
        action="incoming_callback",
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
            "call_id": payload.get("callid") or payload.get("call_id") or payload.get("callId") or payload.get("call_id"),
            "payload": payload,
        },
    )
    return JsonResponse({"ok": True})
