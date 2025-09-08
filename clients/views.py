from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
from clients.models import Client, StageTemplate
from django.contrib.auth.views import LoginView
from payments.models import Contract, InstallmentPlan
from django.shortcuts import redirect




class CustomLoginView(LoginView):
    template_name = 'login.html'


@login_required
def client_dashboard(request):
    client = request.user.client

    contract = Contract.objects.filter(client=client).first()
    installment_plan = InstallmentPlan.objects.filter(contract=contract).first() if contract else None
    installment_payments = installment_plan.payments.all().order_by('number') if installment_plan else []

    current_stage = client.stage
    all_stages = StageTemplate.objects.all()
    total_stages = all_stages.count()

    passed_stages = StageTemplate.objects.filter(order__lt=current_stage.order) if current_stage else StageTemplate.objects.none()
    passed_count = passed_stages.count() + (1 if current_stage else 0)
    
    progress_percent = int((passed_count / total_stages) * 100) if total_stages > 0 else 0

    context = {
        'client_name': str(client),
        'current_stage': current_stage.name if current_stage else "Не определена",
        'current_stage_id': current_stage.id if current_stage else None,
        'current_stage_order': current_stage.order if current_stage else 0,
        'all_stages': all_stages,
        'passed_stages': passed_stages,
        'contract': contract,
        'installment_plan': installment_plan,
        'installment_payments': installment_payments,
        'progress_percent': progress_percent,
    }
    return render(request, 'clientnew.html', context)


@login_required
def redirect_handler(request):
    if request.user.is_staff or request.user.is_superuser:
        return redirect('admin_dashboard')  
    else:
        return redirect('client_dashboard')


def referral_page(request):
    client = get_object_or_404(Client, user=request.user)
    return render(request, "referral.html", {"client": client})