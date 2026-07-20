from django.conf import settings
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_GET
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import Http404, HttpResponseForbidden, JsonResponse
from datetime import datetime, date
from django.utils import timezone

from leadreport.services.pick_manager_calls import get_manager_call_stats
from .models import SalesManager


def is_admin(user):
    return user.is_staff or user.is_superuser


def _check_internal_token(request):
    """Простая защита internal-эндпоинтов общим секретом для сервис-сервис вызовов.
    Если LEADREPORT_INTERNAL_API_TOKEN не задан в settings — эндпоинт открыт (только для локального прототипа)."""
    expected = getattr(settings, "LEADREPORT_INTERNAL_API_TOKEN", "")
    if not expected:
        return True
    provided = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    return provided == expected


def _sales_manager_to_dict(manager: SalesManager) -> dict:
    return {
        "id": manager.pk,
        "name": manager.name,
        "email": manager.email,
        "is_active": manager.is_active,
        "megafon_user": manager.megafon_user,
        "megafon_group": manager.megafon_group,
        "megafon_clid": manager.megafon_clid,
    }


@require_GET
def internal_sales_managers_list(request):
    if not _check_internal_token(request):
        return HttpResponseForbidden("invalid internal token")
    managers = SalesManager.objects.filter(is_active=True).order_by("name")
    return JsonResponse([_sales_manager_to_dict(m) for m in managers], safe=False)


@require_GET
def internal_sales_manager_lookup(request):
    if not _check_internal_token(request):
        return HttpResponseForbidden("invalid internal token")
    email = (request.GET.get("email") or "").strip()
    if not email:
        return JsonResponse({"detail": "email query param is required"}, status=400)
    manager = SalesManager.objects.filter(email__iexact=email).first()
    if not manager:
        return JsonResponse({"detail": "not found"}, status=404)
    return JsonResponse(_sales_manager_to_dict(manager))


@login_required
@require_GET
def lead_my_stats_page(request):
    """Личный кабинет менеджера — показывает статистику по своей SalesManager записи"""
    try:
        sales_profile = request.user.sales_manager_profile
    except SalesManager.DoesNotExist:
        raise Http404("У вас нет профиля менеджера продаж")

    today = date.today()
    start_str = request.GET.get("start")
    end_str   = request.GET.get("end")

    if start_str and end_str:
        try:
            start = datetime.strptime(start_str, "%Y-%m-%dT%H:%M")
            end   = datetime.strptime(end_str,   "%Y-%m-%dT%H:%M")
        except ValueError:
            start = datetime.combine(today, datetime.min.time())
            end   = datetime.combine(today, datetime.max.time())
    else:
        start = datetime.combine(today, datetime.min.time())
        end   = datetime.combine(today, datetime.max.time())

    # ← здесь самое важное изменение
    total_time, call_count = get_manager_call_stats(
        sales_profile.bitrix_user_id,   # ← bitrix_user_id, а не django id
        start,
        end
    )

    context = {
        "manager": sales_profile,
        "period_start": start,
        "period_end": end,
        "total_time": total_time or "0 мин",
        "call_count": call_count or 0,
    }
    return render(request, "my_stats.html", context)


@login_required
@require_GET
@user_passes_test(is_admin)
def lead_admin_dashboard(request):
    """Админ — общая статистика по всем активным менеджерам"""
    today = timezone.now().date()
    start_date = request.GET.get("start", today.strftime("%Y-%m-%d"))
    end_date   = request.GET.get("end",   today.strftime("%Y-%m-%d"))

    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end   = datetime.strptime(end_date,   "%Y-%m-%d")
        end = end.replace(hour=23, minute=59, second=59, microsecond=999999)
    except ValueError:
        start = datetime.combine(today, datetime.min.time())
        end = datetime.combine(today, datetime.max.time())

    managers = SalesManager.objects.filter(
        is_active=True,
        bitrix_user_id__isnull=False
    ).order_by("name")

    stats = []
    for mgr in managers:
        tt, cc = get_manager_call_stats(mgr.bitrix_user_id, start, end)
        stats.append({
            "manager": mgr,
            "total_time": tt or "0 мин",
            "call_count": cc or 0,
        })

    context = {
        "stats": stats,
        "period_start": start.date(),
        "period_end": end.date(),
    }
    return render(request, "lead_admin_dashboard.html", context)


@login_required
@require_GET
@user_passes_test(is_admin)
def lead_admin_manager_detail(request, manager_id):
    """Админ смотрит детальную статистику одного менеджера"""
    manager = get_object_or_404(SalesManager, id=manager_id, is_active=True)

    today = timezone.now().date()
    start_str = request.GET.get("start")
    end_str   = request.GET.get("end")

    if start_str and end_str:
        try:
            start = datetime.strptime(start_str, "%Y-%m-%dT%H:%M")
            end   = datetime.strptime(end_str,   "%Y-%m-%dT%H:%M")
        except ValueError:
            start = datetime.combine(today, datetime.min.time())
            end   = datetime.combine(today, datetime.max.time())
    else:
        start = datetime.combine(today, datetime.min.time())
        end   = datetime.combine(today, datetime.max.time())

    total_time, call_count = get_manager_call_stats(
        manager.bitrix_user_id,
        start,
        end
    )

    context = {
        "manager": manager,
        "period_start": start,
        "period_end": end,
        "total_time": total_time or "0 мин",
        "call_count": call_count or 0,
    }
    return render(request, "admin_manager_detail.html", context)