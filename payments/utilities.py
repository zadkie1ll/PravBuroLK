from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import JsonResponse
import json
import os
import re
from django.utils import timezone
from datetime import datetime, timedelta
import requests  # заменяем httpx на requests


BITRIX_WEBHOOK_URL = "https://prav-buro.bitrix24.ru/rest/24/pa1x5irnfpbcnh27/"

def get_deal_data_from_bitrix(post_data):
    """
    Извлекает ID сделки из POST-данных Bitrix24 и возвращает данные сделки
    """
    document_id_2 = post_data.get('document_id[2]')
    if not document_id_2:
        return None, 'document_id[2] not found'

    deal_id_match = re.search(r'DEAL_(\d+)', document_id_2)
    if not deal_id_match:
        return None, 'Invalid deal ID format'

    deal_id = deal_id_match.group(1)

    # Подставь актуальный вебхук и пользователя
    webhook_url = f"{BITRIX_WEBHOOK_URL}crm.deal.get.json?ID={deal_id}"
    response = requests.get(webhook_url)

    if response.status_code != 200:
        return None, f"Bitrix24 request failed with status {response.status_code}"

    try:
        deal_data = response.json().get('result', {})
        return deal_data, None
    except json.JSONDecodeError:
        return None, 'Invalid JSON response from Bitrix'
    
    
def russian_to_translit(text):
    translit_dict = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 
        'е': 'e', 'ё': 'yo', 'ж': 'zh', 'з': 'z', 'и': 'i', 
        'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n', 
        'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 
        'у': 'u', 'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 
        'ш': 'sh', 'щ': 'shch', 'ъ': '', 'ы': 'y', 'ь': '', 
        'э': 'e', 'ю': 'yu', 'я': 'ya',
        'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'G', 'Д': 'D', 
        'Е': 'E', 'Ё': 'Yo', 'Ж': 'Zh', 'З': 'Z', 'И': 'I', 
        'Й': 'Y', 'К': 'K', 'Л': 'L', 'М': 'M', 'Н': 'N', 
        'О': 'O', 'П': 'P', 'Р': 'R', 'С': 'S', 'Т': 'T', 
        'У': 'U', 'Ф': 'F', 'Х': 'Kh', 'Ц': 'Ts', 'Ч': 'Ch', 
        'Ш': 'Sh', 'Щ': 'Shch', 'Ъ': '', 'Ы': 'Y', 'Ь': '', 
        'Э': 'E', 'Ю': 'Yu', 'Я': 'Ya'
    }
    translit_text = ''.join(translit_dict.get(char, char) for char in text)
    return translit_text