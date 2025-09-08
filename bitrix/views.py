from django.shortcuts import render, get_object_or_404, redirect
from clients.models import Client, Application


def referral_landing(request, referral_code):
    """
    Страница лендинга по реферальной ссылке.
    """
    client = get_object_or_404(Client, referral_code=referral_code)
    
    # Сохраняем в сессии ID реферера, чтобы потом связать заявку
    request.session["referral_client_id"] = client.id

    return render(request, "referral_landing.html", {"client": client})


def referral_submit(request):
    """
    Минимальная логика: создаём только заявку, остальное будет позже.
    """
    if request.method == "POST":
        name = request.POST.get("name")
        phone = request.POST.get("phone")

        referral_owner = None
        ref_id = request.session.get("referral_client_id")
        if ref_id:
            referral_owner = Client.objects.filter(id=ref_id).first()

        # создаём заявку
        Application.objects.create(
            name=name,
            phone=phone,
            referral_owner=referral_owner
        )

        # перенаправление на страницу успеха (можно сделать свою)
        return redirect("application_success")

    # если GET-запрос — просто редирект на главную
    return redirect("referral_landing_home")


def application_success(request):
    return render(request, "application_success.html")