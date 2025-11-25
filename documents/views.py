import os
import logging
from django.http import HttpResponse, Http404, JsonResponse
from django.shortcuts import render
from django.conf import settings
from .services.document_pipeline import DocumentPipeline
from pathlib import Path

from django.shortcuts import render,get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import Http404
from decimal import Decimal
import requests
from django.forms.models import model_to_dict
from docx import Document
from docx.shared import Pt, Inches
from docx.oxml.ns import qn
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import json
import re
import base64
import telebot
import os
from django.conf import settings
from django.db.models import Sum
import traceback
from django.utils.timezone import now


WEBHOOK_URL = "https://prav-buro.bitrix24.ru/rest/24/vszzr53045oedn5m/"

logger = logging.getLogger(__name__)


def generate_document(request):
    if request.method != "POST":
        raise Http404("Этот эндпоинт принимает только POST-запросы.")

    context = request.POST.dict()

    creditors = request.POST.getlist("creditors[]")
    amounts = request.POST.getlist("amounts[]")

    debts = []
    total_debt = 0

    # собираем долги
    for creditor, amount in zip(creditors, amounts):
        try:
            debt_value = float(amount)
        except ValueError:
            debt_value = 0

        total_debt += debt_value

        debts.append({
            "creditor": creditor,
            "amount": debt_value,   # число, а не строка
        })

    # считаем общий платёж = 10%
    total_pay = round(total_debt * 0.10, 2)

    # считаем выплату каждому
    for entry in debts:
        if total_debt > 0:
            proportion = entry["amount"] / total_debt
        else:
            proportion = 0

        entry["payment"] = round(total_pay * proportion, 2)

    # добавляем в контекст
    context["debts"] = debts
    context["total_pay"] = total_pay
    context["total_debt"] = total_debt

    # === остальная часть без изменений ===

    template_path = os.path.join(
        settings.BASE_DIR,
        "documents",
        "templates_src",
        "test_template.docx"
    )

    output_dir = os.path.join(settings.MEDIA_ROOT, "generated_docs")
    os.makedirs(output_dir, exist_ok=True)

    output_path = os.path.join(output_dir, "generated_document.docx")

    pipeline = DocumentPipeline(template_path, context)
    pipeline.run()
    pipeline.save(output_path)

    with open(output_path, "rb") as file:
        response = HttpResponse(
            file.read(),
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        response['Content-Disposition'] = 'attachment; filename="generated_document.docx"'
        return response


def document_form(request):
    """
    Просто рендерит страницу — форма должна отправлять в generate_document.
    """
    return render(request, "document_form.html")




@csrf_exempt
def dogovor(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Only POST allowed'}, status=405)

    logger.error(f"INCOMING POST: {request.POST}")

    # --- Получение ID сделки ---
    document_id_2 = request.POST.get('document_id[2]')
    if not document_id_2:
        return JsonResponse({'status': 'error', 'message': 'document_id[2] missing'}, status=400)

    m = re.search(r"DEAL_(\d+)", document_id_2)
    if not m:
        return JsonResponse({'status': 'error', 'message': 'Invalid deal ID'}, status=400)

    deal_id = m.group(1)
    deal_url = f"{WEBHOOK_URL}crm.deal.get.json?ID={deal_id}"

    # --- Получение сделки ---
    try:
        deal_resp = requests.get(deal_url, timeout=10)
        logger.error(f"DEAL RESPONSE: {deal_resp.text}")

        deal_data = deal_resp.json().get("result")
        if not deal_data:
            return JsonResponse({'status': 'error', 'message': 'Deal not found'}, status=404)

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'Deal fetch error: {e}'}, status=500)

    # --- Подготовка данных ---
    try:
        contact_id = deal_data.get("CONTACT_ID")
        phone_number = get_phone_number(contact_id) if contact_id else "00000000000"

        fio = deal_data.get("TITLE", "")
        fio_parts = fio.split()

        last_name  = fio_parts[0] if len(fio_parts) > 0 else ""
        first_name = fio_parts[1] if len(fio_parts) > 1 else ""
        mid_name   = fio_parts[2] if len(fio_parts) > 2 else ""

        contract = {
            "номер договора": deal_data.get('UF_CRM_1745892727271', "000"),
            "ФИО": fio,
            "фамилия": last_name,
            "имя": first_name,
            "отчество": mid_name,
            "дата рождения": format_date(deal_data.get('UF_CRM_1745888327609')),
            "серия": deal_data.get('UF_CRM_1745889060779', ''),
            "номер": deal_data.get('UF_CRM_1745889067225', ''),
            "кем": deal_data.get('UF_CRM_1745889085935', ''),
            "дата выдачи": format_date(deal_data.get('UF_CRM_1754384630146')),
            "код": deal_data.get('UF_CRM_1745889094660', ''),
            "место рождения": deal_data.get('UF_CRM_1745889105838', ''),
            "адрес регистрации": deal_data.get('UF_CRM_1745893079148', ''),
            "номер телефона": phone_number,
            "сумма юристы": str(int(float(deal_data.get('OPPORTUNITY', 0)))),
            "сумма бонус": deal_data.get('UF_CRM_1742457114242', "0").split("|")[0],
            "Первый платеж": deal_data.get('UF_CRM_1742468532579', "0").split("|")[0],
            "today": datetime.today().strftime("%d.%m.%Y"),
            "data": datetime.today().strftime("%m/%Y"),
            "количество платежей": deal_data.get('UF_CRM_1742480133860', "1"),
            "скидка": deal_data.get('UF_CRM_1742457148727', "0").split("|")[0],
            "дата начала платежей": format_date(deal_data.get('UF_CRM_1742468566169')),
            "Число для оплаты": deal_data.get('UF_CRM_1745893194511', "1"),
        }

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'Data preparation error: {e}'}, status=500)

    # --- Расчёт платежей ---
    try:
        total = int(contract["сумма юристы"]) + int(contract["сумма бонус"])
        num = int(contract["количество платежей"])
        first = int(contract["Первый платеж"])
        discount = int(contract["скидка"])
        start_date = contract["дата начала платежей"]
        second_day = contract["Число для оплаты"]

        payments = calculate_payments(
            num, total, discount, start_date, first,
            second_payment_day=second_day
        )

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'Payment calc error: {e}'}, status=500)

    # --- KРОССПЛАТФОРМЕННЫЕ ПУТИ ---
    if os.name == "nt":
        BASE = Path(r"C:\Apps\lkNewGen\pravburo\documents")
    else:
        BASE = Path("/home/zadkiel/projects/PravBuroLK/documents")

    template = BASE / "templates_src" / "template_2.docx"
    output = BASE / "generated_docs" / f"dogovor_{deal_id}.docx"

    logger.error(f"TEMPLATE PATH: {template}")
    logger.error(f"OUTPUT PATH: {output}")

    # Проверка шаблона
    if not template.exists():
        return JsonResponse({'status': 'error', 'message': f'Template not found: {template}'}, status=500)

    # --- Генерация договора ---
    try:
        output.parent.mkdir(parents=True, exist_ok=True)

        generate_contract(contract, str(template), str(output), payments)

        logger.error(f"GENERATED FILE EXISTS: {output.exists()}")
        if output.exists():
            logger.error(f"FILE SIZE: {output.stat().st_size} bytes")

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'Doc generation error: {e}'}, status=500)

    # --- Загрузка в Bitrix ---
    try:
        result = upload_to_bitrix(
            deal_id,
            str(output),
            'UF_CRM_1745892619372',
            payments
        )
        logger.error(f"BITRIX UPLOAD RESULT: {result}")

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'Upload error: {e}'}, status=500)

    return JsonResponse({'status': 'success', 'message': 'Document generated & uploaded'})

def calculate_payments(num_payments, total_amount, discount, start_date, first_payment, second_payment_day):
    if num_payments == 1 and first_payment >= (total_amount - discount):
        return [[1, start_date, f"{first_payment:.2f}"]]

    remaining_amount = (total_amount - discount) - first_payment
    remaining_payments = num_payments - 1

    if remaining_payments == 0:
        return [[1, start_date, f"{first_payment:.2f}"]]

    payment_amount = round(remaining_amount / remaining_payments, -2)
    
    adjusted_total = first_payment + payment_amount * (remaining_payments - 1)
    last_payment = (total_amount - discount) - adjusted_total 

    first_date = datetime.strptime(start_date, "%d.%m.%Y").date()
    table_data = [[1, first_date.strftime("%d.%m.%Y"), f"{first_payment:.2f}"]]

    second_payment_day = int(second_payment_day)  
    second_date = (first_date + relativedelta(months=1)).replace(day=second_payment_day)

    while second_date.day != second_payment_day:
        second_date -= relativedelta(days=1)

    table_data.append([2, second_date.strftime("%d.%m.%Y"), f"{payment_amount:.2f}"])

    current_date = second_date
    for i in range(2, num_payments - 1):  
        current_date += relativedelta(months=1)
        while current_date.day != second_payment_day:
            current_date -= relativedelta(days=1)
        
        table_data.append([i + 1, current_date.strftime("%d.%m.%Y"), f"{payment_amount:.2f}"])

    current_date += relativedelta(months=1)
    while current_date.day != second_payment_day:
        current_date -= relativedelta(days=1)

    table_data.append([num_payments, current_date.strftime("%d.%m.%Y"), f"{last_payment:.2f}"])

    return table_data

def format_currency(amount):
    return f"{amount:,.2f}".replace(",", " ")



def generate_contract(data, template_path, output_path, payments):
    today = datetime.now().strftime("%d.%m.%Y")
    data["today"] = today
    discount = int(data.get("скидка", 0))

    if data.get('сумма бонус', '') == '':
        data['сумма бонус'] = '0'

    fio_parts = data.get("ФИО", "").split()
    if len(fio_parts) < 3:
        raise ValueError(f"ФИО должно содержать минимум 3 части (Фамилия Имя Отчество), получили: {data.get('ФИО')}")

    data["инициалы"] = f"{fio_parts[0]} {fio_parts[1][0]}. {fio_parts[2][0]}."

    data['сумма юристы'] = str(int(data['сумма юристы']) - discount)
    data["сумма"] = str(int(data["сумма бонус"]) + int(data["сумма юристы"]))
    data["words_sum"] = number_to_words(int(data['сумма юристы']))

    # --- Проверка шаблона ---
    if not os.path.exists(template_path):
        raise FileNotFoundError(f"Template not found: {template_path}")

    doc = Document(template_path)
    replace_text_in_paragraphs(doc, data)
    insert_table_after_heading(doc, payments)

    doc.save(output_path)
    logger.error(f"Document saved: {output_path}")

def apply_style_to_runs(paragraph):
    """Применяет стиль Montserrat 10pt ко всем runs в параграфе."""
    for run in paragraph.runs:
        apply_montserrat_to_run(run)


def set_run_font(run, font_name='Montserrat', font_size=10):
    """Устанавливает шрифт и размер для одного run."""
    run.font.name = font_name
    run.font.size = Pt(font_size)
    rFonts = run._element.rPr.rFonts
    rFonts.set(qn('w:ascii'), font_name)
    rFonts.set(qn('w:hAnsi'), font_name)
    rFonts.set(qn('w:cs'), font_name)
    rFonts.set(qn('w:eastAsia'), font_name)


def replace_text_in_paragraphs(doc, data):
    """Заменяет плейсхолдеры вида {{ключ}} на значения из data во всём документе."""
    def process_paragraph(paragraph):
        full_text = paragraph.text
        for key, value in data.items():
            placeholder = f"{{{{{key}}}}}"
            if value is None:
                value = ""
            full_text = full_text.replace(placeholder, str(value))

        if full_text != paragraph.text:
            # очищаем старые runs
            for _ in range(len(paragraph.runs)):
                paragraph.runs[0].clear()
                paragraph.runs[0]._element.getparent().remove(paragraph.runs[0]._element)

            # создаём новый run с заменённым текстом
            run = paragraph.add_run(full_text)
            set_run_font(run)

    # Параграфы вне таблиц
    for paragraph in doc.paragraphs:
        process_paragraph(paragraph)

    # Параграфы внутри таблиц
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    process_paragraph(paragraph)


def apply_style_to_table_cells(doc):
    """Применяет шрифт Montserrat 10pt ко всем runs в таблицах документа."""
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    for run in paragraph.runs:
                        apply_montserrat_to_run(run)


def insert_table_after_heading(doc, table_data):
    """Вставляет таблицу после заголовка `ГРАФИК ПЛАТЕЖЕЙ`."""
    heading_text = "ГРАФИК ПЛАТЕЖЕЙ"

    for paragraph in doc.paragraphs:
        if heading_text in paragraph.text:
            table = doc.add_table(rows=len(table_data) + 1, cols=3)
            table.style = "Table Grid"

            headers = ["П/П", "Дата платежа", "Сумма платежа"]
            for col_idx, header in enumerate(headers):
                cell = table.cell(0, col_idx)
                cell.text = header
                run = cell.paragraphs[0].runs[0]
                run.font.bold = True
                cell.paragraphs[0].alignment = 1  # по центру

            for row_idx, row_data in enumerate(table_data, start=1):
                for col_idx, cell_data in enumerate(row_data):
                    cell = table.cell(row_idx, col_idx)
                    if cell_data is None:
                        cell_data = ""
                    if col_idx == 2:
                        try:
                            cell_data = str(int(float(cell_data)))
                        except:
                            cell_data = str(cell_data)
                    cell.text = str(cell_data)
                    cell.paragraphs[0].alignment = 1  # по центру

            paragraph._element.addnext(table._element)
            break


def replace_placeholders_in_runs(runs, data):
    """Заменяет плейсхолдеры в конкретных runs."""
    for run in runs:
        original_text = run.text
        for key, value in data.items():
            placeholder = f"{{{{{key}}}}}"
            if value is None:
                value = ""
            if placeholder in original_text:
                run.text = original_text.replace(placeholder, str(value))
                apply_montserrat_to_run(run)


def apply_montserrat_to_run(run):
    """Применяет шрифт Montserrat 10pt к одному run."""
    run.font.name = 'Montserrat'
    run.font.size = Pt(10)

    rFonts = run._element.rPr.rFonts
    rFonts.set(qn('w:ascii'), 'Montserrat')
    rFonts.set(qn('w:hAnsi'), 'Montserrat')
    rFonts.set(qn('w:cs'), 'Montserrat')
    rFonts.set(qn('w:eastAsia'), 'Montserrat')
    
    
    
def get_phone_number(contact_id):
    """Получает номер телефона по contact_id из Битрикс24"""
    contact_url = f"{WEBHOOK_URL}crm.contact.get.json?ID={contact_id}"

    response = requests.get(contact_url)
    
    if response.status_code == 200:
        try:
            contact_data = response.json().get('result', {})
            phone_list = contact_data.get("PHONE", [])
            if phone_list:
                return phone_list[0].get("VALUE", "")  
        except requests.exceptions.JSONDecodeError as e:
            return str(e)

    return ""



def format_date(date_str):
    if not date_str:
        return ""
    try:
        return datetime.fromisoformat(date_str).strftime("%d.%m.%Y")
    except ValueError:
        return date_str
    
    

def upload_to_bitrix(deal_id, file_path, field_id, payment_table):
    """Загрузка файла в сделку Bitrix через JSON + fileData"""

    if not os.path.exists(file_path):
        return {"status": "error", "message": f"Файл не найден: {file_path}"}

    # Кодируем файл в base64
    with open(file_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")

    # Получаем второй платёж (если есть)
    try:
        second_payment = payment_table[1][2]
    except Exception:
        second_payment = None

    # Формируем payload в ТОМ ВИДЕ, КОТОРЫЙ Bitrix принимает
    fields = {
        field_id: {
            "fileData": [os.path.basename(file_path), encoded]
        }
    }

    # Добавляем поле с оплатой, если оно есть
    if second_payment is not None:
        fields["UF_CRM_1745841297007"] = second_payment

    payload = {
        "id": deal_id,
        "fields": fields
    }

    url = f"{WEBHOOK_URL}crm.deal.update.json"
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


def number_to_words(num):
    if num == 0:
        return "ноль"

    units = (
        "", "один", "два", "три", "четыре", "пять",
        "шесть", "семь", "восемь", "девять"
    )
    teens = (
        "десять", "одиннадцать", "двенадцать", "тринадцать",
        "четырнадцать", "пятнадцать", "шестнадцать",
        "семнадцать", "восемнадцать", "девятнадцать"
    )
    tens = (
        "", "", "двадцать", "тридцать", "сорок",
        "пятьдесят", "шестьдесят", "семьдесят",
        "восемьдесят", "девяносто"
    )
    hundreds = (
        "", "сто", "двести", "триста", "четыреста",
        "пятьсот", "шестьсот", "семьсот", "восемьсот",
        "девятьсот"
    )
    thousands_forms = ("тысяча", "тысячи", "тысяч")
    millions_forms = ("миллион", "миллиона", "миллионов")
    
    
    
    
    
def parse_creditors_and_calculate(request):
    """
    Парсит данные из формы:
        creditors[] — имена кредиторов
        amounts[]   — суммы долгов

    Возвращает:
        creditors_data — список структур:
            { "name": str, "debt": float, "pay": float }
        total_debt — общий долг
        total_pay — общая сумма выплат (10%)
    """

    creditor_names = request.POST.getlist("creditors[]")
    creditor_amounts = request.POST.getlist("amounts[]")

    creditors_data = []
    total_debt = 0

    # 1. Парсинг и валидация
    for name, amount in zip(creditor_names, creditor_amounts):
        if not name.strip():
            continue  # пропускаем пустые строки

        try:
            debt = float(amount)
        except ValueError:
            debt = 0

        creditors_data.append({
            "name": name.strip(),
            "debt": debt
        })
        total_debt += debt

    # 2. Расчёт выплат
    total_pay = round(total_debt * 0.10, 2)

    for c in creditors_data:
        if total_debt > 0:
            proportion = c["debt"] / total_debt
        else:
            proportion = 0

        c["pay"] = round(total_pay * proportion, 2)

    return creditors_data, total_debt, total_pay