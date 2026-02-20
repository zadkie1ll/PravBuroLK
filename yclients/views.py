from django.shortcuts import render
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from dotenv import load_dotenv
import os
import json
import requests

load_dotenv()

@csrf_exempt
def yclients_webhook(request):
    if request.method == 'POST':
        try:
            tg_bot_token = os.getenv("YCLIENTS_BOT_TOKEN")  # Замените на правильный ключ, если нужно
            tg_chat_id = os.getenv("YCLIENTS_TG_CHAT_ID")  # Добавьте в .env ваш chat_id (ID чата или канала в TG)

            if not tg_bot_token or not tg_chat_id:
                return HttpResponse("Ошибка: Токен бота или chat_id не указаны в env", status=500)

            # Читаем JSON из тела запроса
            body = request.body.decode('utf-8')
            data = json.loads(body)

            # Извлекаем ключевые данные из вебхука YClients (на основе типичной структуры)
            # Пример: data['data']['client']['name'], data['data']['client']['phone'], data['data']['date'], etc.
            client_name = data.get('data', {}).get('client', {}).get('name', 'Неизвестно')
            client_phone = data.get('data', {}).get('client', {}).get('phone', 'Неизвестно')
            appointment_date = data.get('data', {}).get('date', 'Неизвестно')
            services = data.get('data', {}).get('services', [{}])[0].get('title', 'Неизвестно')  # Первая услуга

            # Формируем текст уведомления
            message_text = (
                f"Новая запись в YClients!\n"
                f"Клиент: {client_name}\n"
                f"Телефон: {client_phone}\n"
                f"Дата: {appointment_date}\n"
                f"Услуга: {services}"
            )

            # Отправляем сообщение в Telegram
            tg_url = f"https://api.telegram.org/bot{tg_bot_token}/sendMessage"
            payload = {
                'chat_id': tg_chat_id,
                'text': message_text,
                'parse_mode': 'HTML'  # Опционально, для форматирования
            }
            response = requests.post(tg_url, data=payload)

            if response.status_code == 200:
                return HttpResponse("Уведомление отправлено", status=200)
            else:
                return HttpResponse(f"Ошибка отправки в TG: {response.text}", status=500)

        except json.JSONDecodeError:
            return HttpResponse("Неверный JSON", status=400)
        except Exception as e:
            return HttpResponse(f"Ошибка: {str(e)}", status=500)

    return HttpResponse("Метод не поддерживается", status=405)