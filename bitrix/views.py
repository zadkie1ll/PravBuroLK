from django.shortcuts import render, redirect
from django.http import Http404
from django.contrib.contenttypes.models import ContentType
from clients.models import Client, Employee, Application, ReferralClick
import telebot
from django.http import JsonResponse, HttpResponse
from .generate_template import generate_pdf
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils import timezone
import os
from .utils import pick, bitrix_checkbox_to_bool, BitrixClient
from documents.views import get_deal_data_from_bitrix
import base64
import requests
import tempfile

BITRIX_WEBHOOK_URL = "https://prav-buro.bitrix24.ru/rest/24/pa1x5irnfpbcnh27/"


BOT_TOKEN = "8208949436:AAEIzi6eP5R04crpwpIchWnpqCCFv8TROvY"
CHAT_ID = "-4907127148"
bot = telebot.TeleBot(BOT_TOKEN)



def upload_to_bitrix(deal_id, file_path, field_id, payment_table):
    """Загрузка файла в сделку Bitrix через JSON + fileData"""

    if not os.path.exists(file_path):
        return {"status": "error", "message": f"Файл не найден: {file_path}"}

    with open(file_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")

    try:
        second_payment = payment_table[1][2]
    except Exception:
        second_payment = None

    fields = {
        field_id: {
            "fileData": [os.path.basename(file_path), encoded]
        }
    }

    if second_payment is not None:
        fields["UF_CRM_1745841297007"] = second_payment

    payload = {
        "id": deal_id,
        "fields": fields
    }

    url = f"{BITRIX_WEBHOOK_URL}crm.deal.update.json"
    response = requests.post(url, json=payload)

    try:
        result = response.json()
    except:
        return {
            "status": "error",
            "message": "Bitrix вернул не-JSON",
            "raw": response.text
        }

    if result.get("error"):
        return {
            "status": "error",
            "message": result.get("error_description", "Ошибка Bitrix"),
            "details": result
        }

    return {"status": "success", "message": "Файл загружен"}


def save_pdf_temp(pdf_bytes: bytes, filename: str) -> str:
    """
    Сохраняет pdf_bytes во временный файл и возвращает путь.
    """
    tmp_dir = tempfile.gettempdir()
    path = os.path.join(tmp_dir, filename)
    with open(path, "wb") as f:
        f.write(pdf_bytes)
    return path

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

    if sort_type == "clicks":
        stats.sort(key=lambda x: x["clicks"], reverse=True)
    else:
        stats.sort(key=lambda x: x["applications"], reverse=True)

    return render(request, "referral_stats.html", {
        "stats": stats,
        "filter": filter_type,
        "sort": sort_type,
    })
    
    
    
    
    
    
    







#пдф для ОП---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------



@csrf_exempt
@require_POST
def build_consultation(request):
    """
    Принимает POST от Битрикса, достаёт сделку,
    собирает payload и возвращает готовый PDF.
    """
    try:
        post_data = request.POST.dict()

        deal_data, error = get_deal_data_from_bitrix(post_data)
        if error:
            return JsonResponse({"error": error}, status=400)

        deal_id = pick(deal_data, "ID")
        assigned_id = pick(deal_data, "ASSIGNED_BY_ID")
        if not deal_id:
            return JsonResponse({"error": "Deal ID not found in deal_data"}, status=400)
        if not assigned_id:
            return JsonResponse({"error": "ASSIGNED_BY_ID not found in deal_data"}, status=400)

        b24 = BitrixClient(BITRIX_WEBHOOK_URL)
        try:
            user = b24.get_user_with_photo(int(assigned_id))
        except Exception:
            user = {"NAME": None, "LAST_NAME": None, "PHOTO_URL": None}

        payload = {
            "document": {
                "document_id": f"CONS-{deal_id}",
                "generated_at": timezone.localtime().strftime("%Y-%m-%d %H:%M"),
            },
            "manager": {
                "bitrix_user_id": assigned_id,
                "first_name": user.get("NAME") or "",
                "last_name": user.get("LAST_NAME") or "",
                "photo": user.get("PHOTO_URL"),
            },
            "finance": {
                "debt_amount": pick(deal_data, "UF_CRM_1746616466655"),
                "work_cost": pick(deal_data, "OPPORTUNITY"),
                "work_bonus": pick(deal_data, "UF_CRM_WORK_BONUS_OR_EMPTY"),
                "installment_plan": pick(deal_data, "UF_CRM_1754380522464"),
            },
            "summary": {
                "property": pick(deal_data, "UF_CRM_1754647601622"),
                "deals": pick(deal_data, "UF_CRM_1754647663541"),
                "marriage": pick(deal_data, "UF_CRM_1754647902223"),
                "income": pick(deal_data, "UF_CRM_1770129399154"),
                "children": pick(deal_data, "UF_CRM_1754647671862"),
            },
            "risks": {
                "no_property_loss_risk": bitrix_checkbox_to_bool(pick(deal_data, "UF_CRM_1770130642610")),
                "no_spouse_property_risk": bitrix_checkbox_to_bool(pick(deal_data, "UF_CRM_1770130660552")),
            },
        }

        print(payload)
        
        pdf_bytes = generate_pdf(payload)
        filename = f"CONS-{deal_id}.pdf"

        # 1) сохраняем во временный файл
        tmp_path = None
        try:
            tmp_path = save_pdf_temp(pdf_bytes, filename)

            # payment_table у тебя в этой view сейчас не формируется.
            # Чтобы функция не падала — передаём пустую таблицу.
            upload_result = upload_to_bitrix(
                deal_id=deal_id,
                file_path=tmp_path,
                field_id="UF_CRM_1770371897876",
                payment_table=[],
            )
            print("Bitrix upload result:", upload_result)

        except Exception as e:
            # Не роняем эндпоинт: PDF всё равно отдаём
            print("Bitrix attach failed:", repr(e))

        finally:
            # чистим временный файл
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

        # 2) ВСЕГДА возвращаем PDF
        resp = HttpResponse(pdf_bytes, content_type="application/pdf")
        resp["Content-Disposition"] = f'inline; filename="{filename}"'
        return resp

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)