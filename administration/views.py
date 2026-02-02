from django.shortcuts import render
import json
import random
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from django.utils import timezone

from .models import Ticket, Prize, SpinResult


LOSE_PROBABILITY = 1

def casino_page(request):
    prizes = Prize.objects.filter(is_active=True)

    return render(
        request,
        "casino.html",
        {
            "prizes": prizes
        }
    )
    
@require_POST
def spin_view(request):
    try:
        data = json.loads(request.body)
        code = data.get("code", "").strip().upper()
    except json.JSONDecodeError:
        return JsonResponse(
            {"success": False, "error": "Некорректный запрос"},
            status=400
        )

    if not code:
        return JsonResponse(
            {"success": False, "error": "Неверный код билета"},
            status=400
        )

    with transaction.atomic():
        try:
            ticket = (
                Ticket.objects
                .select_for_update()
                .get(code=code)
            )
        except Ticket.DoesNotExist:
            return JsonResponse(
                {"success": False, "error": "Билет не найден"},
                status=404
            )

        if ticket.is_used:
            return JsonResponse(
                {"success": False, "error": "Этот билет уже использован"},
                status=400
            )

        if hasattr(ticket, "spin_result"):
            return JsonResponse(
                {"success": False, "error": "Результат уже зафиксирован"},
                status=400
            )

        prize = choose_prize()

        # если приз есть — блокируем его
        if prize:
            prize = Prize.objects.select_for_update().get(pk=prize.pk)

            # дополнительная защита
            if not prize.is_active:
                prize = None

        spin_result = SpinResult.objects.create(
            ticket=ticket,
            prize=prize,
            is_win=bool(prize)
        )

        ticket.is_used = True
        ticket.used_at = timezone.now()
        ticket.save(update_fields=["is_used", "used_at"])

        # 🔥 ДЕАКТИВИРУЕМ ПРИЗ ПОСЛЕ ВЫИГРЫША
        if prize:
            prize.is_active = False
            prize.save(update_fields=["is_active"])

    # --- ответ клиенту ---
    if spin_result.is_win:
        return JsonResponse({
            "success": True,
            "result": "win",
            "prize": prize.name,
            "image": prize.image.url
        })

    return JsonResponse({
        "success": True,
        "result": "lose"
    })
    
def choose_prize():
    if random.random() < LOSE_PROBABILITY:
        return None  

    prizes = list(Prize.objects.filter(is_active=True))
    if not prizes:
        return None

    return random.choices(
        prizes,
        weights=[p.chance for p in prizes],
        k=1
    )[0]