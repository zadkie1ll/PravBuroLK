from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
from django.contrib.contenttypes.models import ContentType
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from clients.models import Client, StageTemplate
from django.contrib.auth.views import LogoutView as DjangoLogoutView
from django.contrib.auth.views import LoginView
from payments.models import Contract, InstallmentPlan, ActualPayment
from .models import DashboardVisit
import time
from django.shortcuts import redirect
from django.utils import timezone
from datetime import timedelta
from django.views import View
from clients.services import ClientService
from clients.lawyer_info import get_client_lawyer_info
from django.db import transaction
from .models import Employee
from payments.utilities import get_deal_data_from_bitrix
BITRIX_WEBHOOK_URL = "https://prav-buro.bitrix24.ru/rest/24/pa1x5irnfpbcnh27/"

def confident_police(request):
    return render(request, "policy.html")



def employee_referral_view(request, employee_id):
    employee = get_object_or_404(Employee, id=employee_id)
    ref_link = employee.get_ref_link(request) 
    return render(request, "employee_referral.html", {
        "employee": employee,
        "ref_link": ref_link,
    })


class CustomLoginView(LoginView):
    template_name = 'login.html'

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

@csrf_exempt
@login_required
def client_dashboard(request):
    client = request.user.client
    lawyer_debug_enabled = request.GET.get("lawyer_debug") == "1"
    lawyer_debug_force_refresh = request.GET.get("lawyer_refresh") == "1"

    if lawyer_debug_enabled:
        lawyer_payload = get_client_lawyer_info(
            client.bitrix_id,
            include_debug=True,
            force_refresh=lawyer_debug_force_refresh,
        ) or {}
        lawyer_info = lawyer_payload.get("info")
        lawyer_debug_steps = lawyer_payload.get("debug_steps", [])
    else:
        lawyer_info = get_client_lawyer_info(client.bitrix_id)
        lawyer_debug_steps = []

    content_type = ContentType.objects.get_for_model(client)
    ip_address = request.META.get('REMOTE_ADDR')
    user_agent = request.META.get('HTTP_USER_AGENT', '')

    visit, _ = DashboardVisit.objects.get_or_create(
        owner_content_type=content_type,
        owner_object_id=client.id,
        ip_address=ip_address,
        defaults={'user_agent': user_agent},
    )
    visit.add_visit()

    contract = Contract.objects.filter(client=client).first()
    installment_plan = (
        InstallmentPlan.objects.filter(contract=contract).first()
        if contract else None
    )

    contract_final_amount = None
    if contract:
        contract_final_amount = contract.total_amount - contract.discount

    installment_payments = []
    actual_payments = []

    if installment_plan:
        # 1. Получаем фактические платежи клиента
        actual_payments = list(
            ActualPayment.objects.filter(plan=installment_plan).order_by("payment_date")
        )

        # 2. Создаем копию сумм фактических платежей
        remaining_actual = [p.amount for p in actual_payments]

        # 3. Проходим по платежам рассрочки и распределяем суммы
        for p in installment_plan.payments.order_by("number"):
            amount_paid = 0
            amount_due = p.amount_due

            # Распределяем суммы simple FIFO (только визуально)
            for i, amt in enumerate(remaining_actual):
                if amt <= 0:
                    continue

                to_apply = min(amt, amount_due - amount_paid)
                amount_paid += to_apply
                remaining_actual[i] -= to_apply

                if amount_paid >= amount_due:
                    break

            # Статус
            if amount_paid >= amount_due:
                status = "paid"
            elif p.due_date < timezone.now().date():
                status = "overdue"
            elif 0 < amount_paid < amount_due:
                status = "partial"
            else:
                status = "pending"

            installment_payments.append({
                "id": p.id,
                "number": p.number,
                "due_date": p.due_date,
                "amount_due": amount_due,
                "amount_paid": amount_paid,
                "status": status,
            })

    all_stages = StageTemplate.objects.all().order_by("order")
    current_stage = client.stage
    stages_data = []

    for stage in all_stages:
        if current_stage and stage.order < current_stage.order:
            status = "done"
        elif current_stage and stage.id == current_stage.id:
            status = "current"
        else:
            status = "future"

        stages_data.append({
            "id": stage.id,
            "order": stage.order,
            "name": stage.name,
            "status": status,
        })

    total_stages = len(all_stages)
    passed_stages = sum(1 for s in stages_data if s["status"] in ("done", "current"))
    progress_percent = int((passed_stages / total_stages) * 100) if total_stages > 0 else 0

    embed_url = None
    if current_stage and current_stage.youtube_url:
        embed_url = current_stage.youtube_url.replace("watch?v=", "embed/")

    show_stage_popup = False
    if client.need_stage_popup and not client.stage_popup_shown:
        show_stage_popup = True
        client.stage_popup_shown = True
        client.save(update_fields=["stage_popup_shown"])

    context = {
        "client": client,
        "lawyer_info": lawyer_info,
        "lawyer_debug_enabled": lawyer_debug_enabled,
        "lawyer_debug_steps": lawyer_debug_steps,
        "contract": contract,
        "contract_final_amount": contract_final_amount,
        "installment_plan": installment_plan,
        "installment_payments": installment_payments,
        "stages": stages_data,
        "progress_percent": progress_percent,
        "embed_url": embed_url,
        "acquiring_enabled": client.acquiring_enabled,
        "current_stage": current_stage,  
        "current_stage_order": current_stage.order if current_stage else None,
        "show_stage_popup": show_stage_popup,  
    }

    return render(request, "clientnew.html", context)

@csrf_exempt
def stage_detail(request, slug):
    stage = get_object_or_404(StageTemplate, slug=slug)
    return render(request, "stage_detail.html", {
        "stage": stage,
        "next_stage": stage.get_next()
    })
    
    
@csrf_exempt
@login_required
def redirect_handler(request):
    if request.user.is_staff or request.user.is_superuser:
        return redirect('admin_dashboard')  
    else:
        return redirect('client_dashboard')
    
    
@require_POST
@login_required
def mark_stage_popup_shown(request):
    client = request.user.client
    client.stage_popup_shown = True
    client.need_stage_popup = False
    client.save(update_fields=['stage_popup_shown', 'need_stage_popup'])
    return JsonResponse({"status": "ok"})


@csrf_exempt
def bitrix_deal_webhook(request):
    """
    Обрабатывает входящий вебхук от Битрикс24 при изменении сделки.
    Меняет стадию клиента на основании bitrix_stage_id.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Only POST allowed"}, status=405)

    try:
        post_data = request.POST.dict() or {}
        deal_data, error = get_deal_data_from_bitrix(post_data)

        if error:
            return JsonResponse({"status": "error", "message": error}, status=400)

        bitrix_id = deal_data.get("ID")
        bitrix_stage_id = deal_data.get("STAGE_ID")

        if not bitrix_id or not bitrix_stage_id:
            return JsonResponse({"status": "error", "message": "Missing bitrix_id or bitrix_stage_id"}, status=400)

        try:
            client = Client.objects.get(bitrix_id=bitrix_id)
        except Client.DoesNotExist:
            return JsonResponse({"status": "error", "message": f"Client with bitrix_id={bitrix_id} not found"}, status=404)

        try:
            stage = StageTemplate.objects.get(bitrix_stage_id=bitrix_stage_id)
        except StageTemplate.DoesNotExist:
            return JsonResponse({"status": "error", "message": f"Stage with bitrix_stage_id={bitrix_stage_id} not found"}, status=404)

        with transaction.atomic():
            client.set_stage(stage)

        return JsonResponse({
            "status": "success",
            "message": f"Stage updated to '{stage.name}' for client '{client}'",
            "client_id": client.id,
            "new_stage": stage.name,
        })

    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)




@csrf_exempt
def referral_page(request):
    client = get_object_or_404(Client, user=request.user)
    return render(request, "referral.html", {"client": client})


@method_decorator(csrf_exempt, name="dispatch")
class TestCreateClientView(View):
    """Тестовый вью для проверки ClientService."""

    def post(self, request):
        try:
            unique_username = f"test_user_{int(time.time() * 1000)}"

            client, contract, plan = ClientService.create_client_with_contract(
                username=unique_username,
                password="12345",
                name="Иван",
                surname="Иванов",
                middlename="Иванович",
                email="ivanov@example.com",
                bitrix_id = f"BX123_{int(time.time() * 1000)}",
                total_amount="100000",
                discount="10000",
                first_payment="20000",
                number_of_payments=6,
                preferred_payment_day=10,
            )

            return JsonResponse({
                "client_id": client.id,
                "contract_id": contract.id,
                "plan_id": plan.id,
                "username": client.user.username,
                "message": "Клиент успешно создан"
            })

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)
        
@login_required
def dashboard_stats(request):
    now = timezone.now()

    all_visits = DashboardVisit.objects.all()

    def count_visits(period_start=None):
        count = 0
        for obj in all_visits:
            for visit_time in obj.visits:
                visit_dt = timezone.datetime.fromisoformat(visit_time)
                if not period_start or visit_dt >= period_start:
                    count += 1
        return count

    day_start = now - timedelta(days=1)
    week_start = now - timedelta(weeks=1)
    month_start = now - timedelta(days=30)

    stats = {
        "today": count_visits(day_start),
        "week": count_visits(week_start),
        "month": count_visits(month_start),
        "all_time": count_visits(),
    }

    return render(request, "dashboard_stats.html", {"stats": stats})



class CustomLogoutView(DjangoLogoutView):
    """
    Logout с редиректом по ролям.
    """
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_staff or request.user.is_superuser:
            self.next_page = 'admin_dashboard'
        else:
            self.next_page = 'client_dashboard'

        return super().dispatch(request, *args, **kwargs)
    
@csrf_exempt
@require_POST
def setIsBlocked(request):
    try:
        bitrix_id = request.POST.get("bitrix_id")
        if (not bitrix_id):
            return JsonResponse({
                "status" : 'error',
                "message": "bitrix_id is required"},
                status = 400
                
            )
        try:
            client = Client.objects.get(bitrix_id=bitrix_id)
        except:
            return JsonResponse(
                {
                    "status": "error",
                    "message": "No user with {bitrix_id} id found"
                },
                status=404
            ) 
        with transaction.atomic():
            client.isBlocked = not client.isBlocked
            client.save(update_fields=['isBlocked'])
        return JsonResponse({
            "status": "succeded",
            "message": "user block status is changed"
        },
        status=200)
    except Exception as e:
        return JsonResponse({
            "status": "error",
            "message": str(e)
        }, status=500)
