from django.shortcuts import render, redirect
from django.http import Http404
from django.contrib.contenttypes.models import ContentType
from clients.models import Client, Employee, Application, ReferralClick
import telebot


# 🔑 Telegram настройки
BOT_TOKEN = "8208949436:AAEIzi6eP5R04crpwpIchWnpqCCFv8TROvY"
CHAT_ID = "-4907127148"
bot = telebot.TeleBot(BOT_TOKEN)


def get_client_ip(request):
    """Извлекаем IP-адрес пользователя"""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def referral_landing(request, referral_code):
    """
    Общая реферальная страница:
    - Определяем владельца по referral_code
    - Сохраняем id в session
    - Логируем клик в ReferralClick
    """
    client = Client.objects.filter(referral_code=referral_code).first()
    employee = None
    owner = None

    if client:
        request.session["referral_client_id"] = client.id
        request.session.pop("referral_employee_id", None)
        owner = client
    else:
        employee = Employee.objects.filter(referral_code=referral_code).first()
        if employee:
            request.session["referral_employee_id"] = employee.id
            request.session.pop("referral_client_id", None)
            owner = employee
        else:
            raise Http404("Referral not found")

    # ✅ Логируем клик
    if owner:
        ReferralClick.objects.get_or_create(
            owner_content_type=ContentType.objects.get_for_model(owner),
            owner_object_id=owner.id,
            ip_address=get_client_ip(request),
            defaults={"user_agent": request.META.get("HTTP_USER_AGENT", "")},
        )

    return render(request, "referral_landing.html", {
        "client": client,
        "employee": employee,
    })


def referral_submit(request):
    """
    Обработка формы заявки:
    - Определяем владельца из сессии
    - Создаём Application
    - Отправляем уведомление в Telegram
    """
    if request.method == "POST":
        name = request.POST.get("name")
        phone = request.POST.get("phone")

        referral_owner = None
        if "referral_client_id" in request.session:
            referral_owner = Client.objects.filter(id=request.session["referral_client_id"]).first()
        elif "referral_employee_id" in request.session:
            referral_owner = Employee.objects.filter(id=request.session["referral_employee_id"]).first()

        Application.objects.create(
            name=name,
            phone=phone,
            client=request.user.client if request.user.is_authenticated and hasattr(request.user, "client") else None,
            referral_owner=referral_owner,
        )

        # ✅ Уведомление в Telegram
        try:
            text = f"📩 Новая заявка!\n\n👤 Имя: {name}\n📞 Телефон: {phone}"
            if referral_owner:
                text += f"\n🔗 Источник: {referral_owner}"
            bot.send_message(chat_id=CHAT_ID, text=text)
        except Exception as e:
            print("Ошибка при отправке в Telegram:", e)

        return redirect("application_success")

    return redirect("referral_landing_home")


def application_success(request):
    """Страница успеха"""
    return render(request, "application_success.html")

def referral_stats(request):
    """
    Статистика по реферальным ссылкам с фильтром и сортировкой.
    """
    filter_type = request.GET.get("filter", "all")
    sort_type = request.GET.get("sort", "applications")

    stats = []

    # --- Клиенты ---
    if filter_type in ["all", "clients"]:
        client_ct = ContentType.objects.get_for_model(Client)
        for client in Client.objects.all():
            clicks = ReferralClick.objects.filter(
                owner_content_type=client_ct,
                owner_object_id=client.id,
            ).count()
            apps = Application.objects.filter(
                referral_owner_content_type=client_ct,
                referral_owner_object_id=client.id,
            ).count()
            stats.append({
                "type": "Клиент",
                "name": str(client),
                "ref_link": client.get_ref_link(request),
                "clicks": clicks,
                "applications": apps,
            })

    # --- Сотрудники ---
    if filter_type in ["all", "employees"]:
        employee_ct = ContentType.objects.get_for_model(Employee)
        for emp in Employee.objects.all():
            clicks = ReferralClick.objects.filter(
                owner_content_type=employee_ct,
                owner_object_id=emp.id,
            ).count()
            apps = Application.objects.filter(
                referral_owner_content_type=employee_ct,
                referral_owner_object_id=emp.id,
            ).count()
            stats.append({
                "type": "Сотрудник",
                "name": str(emp),
                "ref_link": emp.get_ref_link(request),
                "clicks": clicks,
                "applications": apps,
            })

    # --- Сортировка ---
    if sort_type == "clicks":
        stats.sort(key=lambda x: x["clicks"], reverse=True)
    else:
        stats.sort(key=lambda x: x["applications"], reverse=True)

    return render(request, "referral_stats.html", {
        "stats": stats,
        "filter": filter_type,
        "sort": sort_type,
    })
