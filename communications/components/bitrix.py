import requests
def send_notification(id, message):
    response = requests.post(f"https://prav-buro.bitrix24.ru/rest/24/kod9fyniu51siemd/im.notify.personal.add.json?USER_ID={id}&MESSAGE={message}")
    print(response.text)