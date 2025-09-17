from django.shortcuts import render, get_object_or_404, redirect
from clients.models import Client, Application
import telebot


BOT_TOKEN = "8208949436:AAEIzi6eP5R04crpwpIchWnpqCCFv8TROvY"
CHAT_ID = "-4907127148"

bot = telebot.TeleBot(BOT_TOKEN)

def referral_landing(request, referral_code):
    client = get_object_or_404(Client, referral_code=referral_code)
    
    request.session["referral_client_id"] = client.id

    return render(request, "referral_landing.html", {"client": client})


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