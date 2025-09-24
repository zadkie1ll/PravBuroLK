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
from payments.models import Contract, InstallmentPlan
from .models import DashboardVisit
import time
from django.shortcuts import redirect
from django.utils import timezone
from datetime import timedelta
from django.views import View
from clients.services import ClientService
from .models import Employee




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
    content_type = ContentType.objects.get_for_model(client)
    ip_address = get_client_ip(request)
    user_agent = request.META.get('HTTP_USER_AGENT', '')

    visit_obj, created = DashboardVisit.objects.get_or_create(
        owner_content_type=content_type,
        owner_object_id=client.id,
        ip_address=ip_address,
        defaults={"user_agent": user_agent}
    )
    visit_obj.add_visit()

    contract = Contract.objects.filter(client=client).first()
    installment_plan = InstallmentPlan.objects.filter(contract=contract).first() if contract else None

    contract_final_amount = None
    if contract:
        contract_final_amount = contract.total_amount - contract.discount

    installment_payments = []
    if installment_plan:
        for p in (
            installment_plan.payments
            .prefetch_related("applications__actual_payment")
            .order_by("number")
        ):
            applied_sum = sum(app.applied_amount for app in p.applications.all())

            if applied_sum >= p.amount_due:
                status = "paid"
            elif p.due_date < timezone.now().date():
                status = "overdue"
            elif 0 < applied_sum < p.amount_due:
                status = "partial"
            else:
                status = "pending"

            installment_payments.append({
                "number": p.number,
                "due_date": p.due_date,
                "amount_due": p.amount_due,
                "amount_paid": applied_sum,
                "status": status,
            })

    current_stage = client.stage
    all_stages = StageTemplate.objects.all()
    total_stages = all_stages.count()

    passed_stages = StageTemplate.objects.filter(order__lt=current_stage.order) if current_stage else StageTemplate.objects.none()
    passed_count = passed_stages.count() + (1 if current_stage else 0)
    progress_percent = int((passed_count / total_stages) * 100) if total_stages > 0 else 0

    embed_url = None
    if current_stage and current_stage.youtube_url:
        embed_url = current_stage.youtube_url.replace("watch?v=", "embed/")

    context = {
        "client_name": str(client),
        "current_stage": current_stage,
        "current_stage_id": current_stage.id if current_stage else None,
        "current_stage_order": current_stage.order if current_stage else 0,
        "all_stages": all_stages,
        "passed_stages": passed_stages,
        "contract": contract,
        "contract_final_amount": contract_final_amount,
        "installment_plan": installment_plan,
        "installment_payments": installment_payments,
        "progress_percent": progress_percent,
        "show_stage_popup": client.need_stage_popup and not client.stage_popup_shown,
        "embed_url": embed_url,
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
        # 1️⃣ пока пользователь ещё авторизован — определяем, куда редиректить
        if request.user.is_staff or request.user.is_superuser:
            self.next_page = 'admin_dashboard'
        else:
            self.next_page = 'client_dashboard'

        # 2️⃣ вызываем обычный dispatch,
        #     который уже внутри post() сделает auth_logout()
        return super().dispatch(request, *args, **kwargs)