from __future__ import annotations

from typing import Any
from leadreport.models import SalesManager
import requests
from django.conf import settings


class MegafonAPIError(Exception):
    pass


class MegafonTelephonyService:
    def __init__(
        self,
        base_url: str | None = "https://vats671653.megapbx.ru/crmapi/v1",
        api_key: str | None = "9fa7e15c-1997-4192-8406-3245d251dce5",
        auth_header: str | None = None,
        auth_mode: str | None = None,
    ):
        self.base_url = (base_url or settings.MEGAFON_VATS_API_URL).rstrip("/")
        self.api_key = api_key or settings.MEGAFON_VATS_API_KEY
        self.auth_header = auth_header or getattr(settings, "MEGAFON_VATS_AUTH_HEADER", "X-CRM-AUTH")
        self.auth_mode = auth_mode or getattr(settings, "MEGAFON_VATS_AUTH_MODE", "header")

    def make_call(
        self,
        *,
        phone: str,
        user: str | None = None,
        group: str | None = None,
        clid: str | None = None,
        show_phone: bool = True,
    ) -> dict[str, Any]:
        if not self.base_url:
            raise MegafonAPIError("Не задан MEGAFON_VATS_API_URL.")
        if not self.api_key:
            raise MegafonAPIError("Не задан MEGAFON_VATS_API_KEY.")
        if not user and not group:
            raise MegafonAPIError("Для исходящего звонка нужно передать megafon_user или megafon_group.")

        payload: dict[str, Any] = {
            "phone": phone,
            "show_phone": bool(show_phone),
            "user": user,
    
        }
        
        headers = {"X-API-KEY": self.api_key}
        params: dict[str, Any] = {}

        if self.auth_mode == "header":
            headers[self.auth_header] = self.api_key
        elif self.auth_mode == "query":
            params["auth"] = self.api_key
        elif self.auth_mode == "body":
            payload["auth"] = self.api_key
        else:
            raise MegafonAPIError(f"Неизвестный режим авторизации МегаФона: {self.auth_mode}")

        try:
            response = requests.post(
                f"{self.base_url}/makecall",
                json=payload,
                headers=headers,
                #params=params,
                timeout=30,
            )
            response.raise_for_status()
        except requests.HTTPError as exc:
            response = exc.response
            details = ""
            if response is not None:
                try:
                    error_payload = response.json()
                except ValueError:
                    error_payload = response.text.strip()
                if error_payload:
                    details = f" Детали ответа: {error_payload}"
            raise MegafonAPIError(f"МегаФон вернул HTTP {response.status_code if response else 'error'}.{details}") from exc
        except requests.RequestException as exc:
            raise MegafonAPIError(f"Ошибка запроса к МегаФону: {exc}") from exc

        data = response.json()
        if not isinstance(data, dict):
            raise MegafonAPIError("МегаФон вернул неожиданный ответ.")
        if not data.get("callid"):
            raise MegafonAPIError(f"МегаФон не вернул callid: {data}")
        return data
