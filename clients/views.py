from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from clients.models import Client, StageTemplate
from django.contrib.auth.views import LoginView
from payments.models import Contract, InstallmentPlan
import time
from django.shortcuts import redirect
from django.utils import timezone
from django.views import View
from clients.services import ClientService



class CustomLoginView(LoginView):
    template_name = 'login.html'

@csrf_exempt
@login_required
def client_dashboard(request):
    client = request.user.client

    contract = Contract.objects.filter(client=client).first()
    installment_plan = InstallmentPlan.objects.filter(contract=contract).first() if contract else None

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

    # стадии клиента
    current_stage = client.stage
    all_stages = StageTemplate.objects.all()
    total_stages = all_stages.count()

    passed_stages = StageTemplate.objects.filter(order__lt=current_stage.order) if current_stage else StageTemplate.objects.none()
    passed_count = passed_stages.count() + (1 if current_stage else 0)
    progress_percent = int((passed_count / total_stages) * 100) if total_stages > 0 else 0

    context = {
        "client_name": str(client),
        "current_stage": current_stage.name if current_stage else "Не определена",
        "current_stage_id": current_stage.id if current_stage else None,
        "current_stage_order": current_stage.order if current_stage else 0,
        "all_stages": all_stages,
        "passed_stages": passed_stages,
        "contract": contract,
        "installment_plan": installment_plan,
        "installment_payments": installment_payments,
        "progress_percent": progress_percent,
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