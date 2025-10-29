import requests
from django.conf import settings


#ЗАЛУПА КОД В ПРОДЕ НЕ ИСПОЛЬЗУЕТСЯ!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!


class AlfaBankAPI:
    def __init__(self, test_mode=True):
        if test_mode:
            self.base_url = settings.ALFA_API_URL_TEST
            self.user = settings.ALFA_USER_TEST
            self.password = settings.ALFA_PASS_TEST
        else:
            self.base_url = settings.ALFA_API_URL_PROD
            self.user = settings.ALFA_USER_PROD
            self.password = settings.ALFA_PASS_PROD

    def register_order(self, order_number, amount, description, return_url, fail_url):
        """
        Создание заказа в Альфа-Банке
        """
        url = f"{self.base_url}/register.do"
        payload = {
            "userName": self.user,
            "password": self.password,
            "orderNumber": order_number,
            "amount": amount,
            "description": description,
            "returnUrl": return_url,
            "failUrl": fail_url,
        }

        response = requests.post(url, data=payload)
        data = response.json()

        return data

    def get_order_status(self, order_id):
        """
        Получение статуса заказа
        """
        url = f"{self.base_url}/getOrderStatusExtended.do"
        payload = {
            "userName": self.user,
            "password": self.password,
            "orderId": order_id,
        }

        response = requests.post(url, data=payload)
        return response.json()
