from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from leadreport.services.pick_manager_calls import get_manager_call_stats
from datetime import datetime
@require_POST
@csrf_exempt
def get_stats(request):
    manager = request.POST.get("manager")
    start_str = request.POST.get("start")
    end_str = request.POST.get("end")

    if not all([manager, start_str, end_str]):
        return JsonResponse({"error": "Missing required parameters"}, status=400)

    try:
        # Parse strings → datetime objects
        # Adjust format if your input ever changes (this matches "2020-01-01 00:00:00")
        start = datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S")
        end   = datetime.strptime(end_str,   "%Y-%m-%d %H:%M:%S")

        total_time, call_count = get_manager_call_stats(
            int(manager),   # make sure it's int
            start,
            end
        )

        return JsonResponse({
            "Общее время за период": total_time,
            "Общее количество звонков за период": call_count,
        }, status=200)

    except ValueError as e:
        # Catches bad date format, invalid manager int, etc.
        return JsonResponse({"error": f"Invalid input: {str(e)}"}, status=400)
    except Exception as e:
        return JsonResponse({"error": f"Server error: {str(e)}"}, status=500)