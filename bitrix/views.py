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
from django.db import transaction
from .models import Region
from .services.regions_sync import sync_regions_from_bitrix_logic
from django.conf import settings
from .services.km_calculator import KmInput, PmValues, calculate_km
from .models import PmRate
import datetime
BITRIX_REGION_FIELD = "UF_CRM_1745886887592"

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
    
    
    
    
    
    
    



@csrf_exempt
@require_POST
def sync_regions_from_bitrix(request):
    try:
        result = sync_regions_from_bitrix_logic()
        return JsonResponse(result)
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)




#пдф для ОП---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------



# UF поля
UF_REGION = "UF_CRM_1745886887592"
UF_SHOW_KM = "UF_CRM_1770730700097"

UF_SALARY = "UF_CRM_1770129399154"
UF_PENSION = "UF_CRM_1770647008781"

UF_CLIENT_NAME = "UF_CRM_1754380684375"
UF_BENEFITS = "UF_CRM_1770646540351"
UF_CHILD_PAYMENTS = "UF_CRM_1770646550503"
UF_ALIMONY = "UF_CRM_1770646560950"
UF_SOCIAL = "UF_CRM_1770646571974"
UF_OTHER = "UF_CRM_1770646605351"

UF_CHILDREN_COUNT = "UF_CRM_1770721913265"


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

        # --- NEW: KM inputs ---
        show_km = bitrix_checkbox_to_bool(pick(deal_data, UF_SHOW_KM))

        region_raw = pick(deal_data, UF_REGION)
        region_id = None
        try:
            if region_raw is not None and str(region_raw).strip() != "":
                region_id = int(str(region_raw).strip())
        except ValueError:
            region_id = None

        # достаём ПМ из БД (если регион не выбран или не заполнен — будет None)
        now = timezone.localtime()
        pm_rate = PmRate.get_for_region_on(region_id, dt=now) if region_id else None

        pm_values = PmValues(
            pm_working=pm_rate.pm_working if pm_rate else 0,
            pm_pensioner=pm_rate.pm_pensioner if pm_rate else 0,
            pm_child=(pm_rate.pm_child if (pm_rate and pm_rate.pm_child is not None) else 0),
        )

        km_json = calculate_km(
            KmInput(
                region_bitrix_id=region_id,
                salary=pick(deal_data, UF_SALARY),
                pension=pick(deal_data, UF_PENSION),
                children_count=pick(deal_data, UF_CHILDREN_COUNT),
                benefits=pick(deal_data, UF_BENEFITS),
                child_payments=pick(deal_data, UF_CHILD_PAYMENTS),
                alimony=pick(deal_data, UF_ALIMONY),
                social=pick(deal_data, UF_SOCIAL),
                other=pick(deal_data, UF_OTHER),
            ),
            pm_values,
        )

        payload = {
            "document": {
                "document_id": f"CONS-{deal_id}",
                "generated_at": pick(deal_data, "DATE_CREATE"),
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
                "client_name": pick(deal_data, UF_CLIENT_NAME) or "Итог",
                "contract" : pick(deal_data, "UF_CRM_1745888352245"),
                "property": pick(deal_data, "UF_CRM_1754647601622"),
                "deals": pick(deal_data, "UF_CRM_1754647663541"),
                "marriage": pick(deal_data, "UF_CRM_1754647902223"),

                "income": pick(deal_data, UF_SALARY),

                "children": pick(deal_data, "UF_CRM_1754647671862"),
                "show_km": show_km,
            },
            "risks": {
                "no_property_loss_risk": bitrix_checkbox_to_bool(pick(deal_data, "UF_CRM_1770130642610")),
                "no_spouse_property_risk": bitrix_checkbox_to_bool(pick(deal_data, "UF_CRM_1770130660552")),
            },

            # --- NEW: KM расчет целиком (для generate_pdf -> шаблона) ---
            "km": km_json,
        }

        print(payload)

        pdf_bytes = generate_pdf(payload)
        filename = f"CONS-{deal_id}.pdf"

        tmp_path = None
        try:
            tmp_path = save_pdf_temp(pdf_bytes, filename)

            upload_result = upload_to_bitrix(
                deal_id=deal_id,
                file_path=tmp_path,
                field_id="UF_CRM_1770371897876",
                payment_table=[],
            )
            print("Bitrix upload result:", upload_result)

        except Exception as e:
            print("Bitrix attach failed:", repr(e))

        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

        resp = HttpResponse(pdf_bytes, content_type="application/pdf")
        resp["Content-Disposition"] = f'inline; filename="{filename}"'
        return resp

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
    
    
    
    
    
    
#KM_CALCULATOR-------------------------------------------------------------------------------------------------------------------------------------------------------
# поля Bitrix
UF_REGION = "UF_CRM_1745886887592"

UF_SALARY = "UF_CRM_1770129399154"
UF_PENSION = "UF_CRM_1770647008781"

UF_BENEFITS = "UF_CRM_1770646540351"
UF_CHILD_PAYMENTS = "UF_CRM_1770646550503"
UF_ALIMONY = "UF_CRM_1770646560950"
UF_SOCIAL = "UF_CRM_1770646571974"
UF_OTHER = "UF_CRM_1770646605351"

UF_CHILDREN_COUNT = "UF_CRM_1770721913265"


@csrf_exempt
@require_POST
def calc_km_for_deal(request):
    """
    Принимает POST от Битрикса, достаёт сделку и возвращает JSON с расчётом конкурсной массы.
    """
    try:
        post_data = request.POST.dict()

        deal_data, error = get_deal_data_from_bitrix(post_data)
        if error:
            return JsonResponse({"ok": False, "error": error}, status=400)

        deal_id = pick(deal_data, "ID")
        assigned_id = pick(deal_data, "ASSIGNED_BY_ID")
        if not deal_id:
            return JsonResponse({"ok": False, "error": "Deal ID not found in deal_data"}, status=400)
        if not assigned_id:
            return JsonResponse({"ok": False, "error": "ASSIGNED_BY_ID not found in deal_data"}, status=400)

        # регион (enum ID из списка)
        region_bitrix_id_raw = pick(deal_data, UF_REGION)
        region_bitrix_id = None
        try:
            # бывает строка
            if region_bitrix_id_raw is not None and str(region_bitrix_id_raw).strip() != "":
                region_bitrix_id = int(str(region_bitrix_id_raw).strip())
        except ValueError:
            region_bitrix_id = None

        # берём ПМ на дату расчёта (можно привязать к дате консультации/создания сделки)
        now = timezone.localtime()
        pm_rate = PmRate.get_for_region_on(region_bitrix_id, dt=now) if region_bitrix_id else None

        pm_values = PmValues(
            pm_working=pm_rate.pm_working if pm_rate else 0,
            pm_pensioner=pm_rate.pm_pensioner if pm_rate else 0,
            pm_child=(pm_rate.pm_child if (pm_rate and pm_rate.pm_child is not None) else 0),
        )

        inp = KmInput(
            region_bitrix_id=region_bitrix_id,
            salary=pick(deal_data, UF_SALARY),
            pension=pick(deal_data, UF_PENSION),
            children_count=pick(deal_data, UF_CHILDREN_COUNT),
            benefits=pick(deal_data, UF_BENEFITS),
            child_payments=pick(deal_data, UF_CHILD_PAYMENTS),
            alimony=pick(deal_data, UF_ALIMONY),
            social=pick(deal_data, UF_SOCIAL),
            other=pick(deal_data, UF_OTHER),
        )

        km_json = calculate_km(inp, pm_values)

        return JsonResponse({
            "ok": True,
            "deal": {
                "id": deal_id,
                "assigned_id": assigned_id,
                "region_bitrix_id": region_bitrix_id,
            },
            "pm_rate": (
                {
                    "effective_from": pm_rate.effective_from.isoformat(),
                    "pm_working": float(pm_rate.pm_working),
                    "pm_pensioner": float(pm_rate.pm_pensioner),
                    "pm_child": float(pm_rate.pm_child) if pm_rate.pm_child is not None else 0.0,
                }
                if pm_rate else None
            ),
            "km": km_json,
        })

    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)
    
@require_POST
@csrf_exempt
def test(request):
    print("Method:", request.method)
    print("Path:", request.path)
    print("GET params:", request.GET)
    print("POST params (form):", request.POST)
    print("FILES:", request.FILES)
    print("Content-Type:", request.headers.get("Content-Type"))
    print("Headers:", dict(request.headers))           # все заголовки

    # ─────────────── Самое важное ───────────────
    try:
        body_bytes = request.body          # ← сырые байты
        print("Raw body (bytes):", body_bytes)
        print("Raw body (str):", body_bytes.decode("utf-8", errors="replace"))
    except Exception as e:
        print("Не удалось прочитать body:", str(e))

    # Если ожидаешь JSON — почти всегда так делают:
    try:
        import json
        data = json.loads(request.body)
        print("Parsed JSON:", data)
    except Exception as e:
        print("Не JSON или пусто/битый:", str(e))

    return HttpResponse("OK", status=200)
