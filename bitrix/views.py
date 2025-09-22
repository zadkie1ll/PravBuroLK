from django.shortcuts import render, get_object_or_404, redirect
from clients.models import Client, Application, Employee
import telebot


BOT_TOKEN = "8208949436:AAEIzi6eP5R04crpwpIchWnpqCCFv8TROvY"
CHAT_ID = "-4907127148"

bot = telebot.TeleBot(BOT_TOKEN)


def referral_landing(request, referral_code):
    """
    Общая реферальная страница:
    - если referral_code принадлежит Client → сохраняем referral_client_id
    - если referral_code принадлежит Employee → сохраняем referral_employee_id
    """

    client = Client.objects.filter(referral_code=referral_code).first()
    employee = None

    if client:
        request.session["referral_client_id"] = client.id
    else:
        employee = Employee.objects.filter(referral_code=referral_code).first()
        if employee:
            request.session["referral_employee_id"] = employee.id
        else:
            # если вообще нет такого кода → 404
            from django.http import Http404
            raise Http404("Referral not found")

    return render(request, "referral_landing.html", {
        "client": client,
        "employee": employee,
    })


def referral_submit(request):
    if request.method == "POST":
        name = request.POST.get("name")
        phone = request.POST.get("phone")

        referral_owner = None
        ref_id = request.session.get("referral_client_id")
        if ref_id:
            referral_owner = Client.objects.filter(id=ref_id).first()

        Application.objects.create(
            name=name,
            phone=phone,
            referral_owner=referral_owner
        )

        try:
            text = f"📩 Новая заявка!\n\n👤 Имя: {name}\n📞 Телефон: {phone}"
            bot.send_message(chat_id=CHAT_ID, text=text)
        except Exception as e:
            print("Ошибка при отправке в Telegram:", e)

        return redirect("application_success")

    return redirect("referral_landing_home")


def application_success(request):
    return render(request, "application_success.html")