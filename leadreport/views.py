from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST
from django.http import JsonResponse
from services.pick_manager_calls import get_manager_call_stats
@require_POST
def get_stats(request):
    manager = request.POST.get("manager")
    start = request.POST.get("start")
    end = request.POST.get("end")
    total_time, call_count = get_manager_call_stats(manager, start, end)
    
    return JsonResponse({
        "Общее время за период": total_time,
        "Общее количество звонков за период": call_count,
    }, status = 200
    )