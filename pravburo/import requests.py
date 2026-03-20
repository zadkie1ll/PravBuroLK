import requests
import json
from collections import defaultdict
import re
import time

# ────────────────────────────────────────────────
# Настройки — подставь свои
# ────────────────────────────────────────────────

WEBHOOK_URL = "https://prav-buro.bitrix24.ru/rest/24/pa1x5irnfpbcnh27/"  
# или https://ВАШ_ПОРТАЛ.bitrix24.ru/rest/USER_ID/HOOK_CODE/

BATCH_SIZE = 50          # сколько контактов за один запрос (max 250)
PAUSE_BETWEEN = 0.4      # пауза между запросами в секундах (чтобы не словить лимит)

# ────────────────────────────────────────────────

def normalize_phone(phone: str) -> str:
    """Приводим номер к единому виду: только цифры + возможно ведущий +"""
    if not phone:
        return ""
    # Убираем всё кроме цифр и +
    cleaned = re.sub(r'[^0-9+]', '', phone.strip())
    # Если начинается не с +, но есть 7/8 → считаем российским
    if cleaned.startswith(('7', '8')) and len(cleaned) in (11, 12):
        cleaned = '+7' + cleaned[1:]
    return cleaned


def get_all_contacts_with_phones():
    url = WEBHOOK_URL + "crm.contact.list"
    contacts_by_phone = defaultdict(list)   # телефон → список контактов

    start = 0
    total_processed = 0

    print("Собираем контакты...")

    while True:
        payload = {
            "select": ["ID", "NAME", "LAST_NAME", "PHONE"],
            "filter": {"!PHONE": False},   # только с хотя бы одним телефоном
            "order": {"ID": "ASC"},
            "start": start
        }

        try:
            response = requests.post(url, json=payload, timeout=15)
            response.raise_for_status()
            data = response.json()

            if not data.get("result"):
                break

            for contact in data["result"]:
                contact_id = contact["ID"]
                name = (contact.get("NAME") or "").strip()
                last = (contact.get("LAST_NAME") or "").strip()
                full_name = f"{name} {last}".strip() or "Без имени"

                phones = contact.get("PHONE", [])
                for ph in phones:
                    val = ph.get("VALUE", "").strip()
                    clean = normalize_phone(val)
                    if clean:
                        contacts_by_phone[clean].append({
                            "id": contact_id,
                            "name": full_name,
                            "phone_raw": val
                        })

            processed = len(data["result"])
            total_processed += processed
            print(f"  обработано {total_processed} контактов...")

            start = data.get("next")
            if start is None:
                break

            time.sleep(PAUSE_BETWEEN)

        except Exception as e:
            print(f"Ошибка на позиции {start}: {e}")
            time.sleep(3)
            continue

    return contacts_by_phone


def print_duplicates(contacts_by_phone):
    print("\n" + "="*70)
    print("Контакты с дублирующимися номерами телефона")
    print("="*70 + "\n")

    found = False

    for phone, items in sorted(contacts_by_phone.items(), key=lambda x: len(x[1]), reverse=True):
        if len(items) <= 1:
            continue

        found = True
        print(f"Телефон: {phone}   →   {len(items)} контактов")
        for item in items:
            print(f"    • ID {item['id']:>6}   {item['name']:<35}   ({item['phone_raw']})")
        print()

    if not found:
        print("Дублей по телефону НЕ НАЙДЕНО")


# ─── Запуск ───────────────────────────────────────

if __name__ == "__main__":
    duplicates_map = get_all_contacts_with_phones()
    print_duplicates(duplicates_map)
    with open("doubles.txt", 'w') as file:
        file.write(f"\nВсего уникальных номеров: {len(duplicates_map)}")