from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional
import requests


class BitrixApiError(RuntimeError):
    pass


@dataclass(frozen=True)
class BitrixClient:
    """
    base_webhook_url example:
    https://prav-buro.bitrix24.ru/rest/24/pa1x5irnfpbcnh27/
    """
    base_webhook_url: str
    timeout: float = 20.0

    def _call(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = self.base_webhook_url.rstrip("/") + f"/{method}.json"
        try:
            r = requests.get(url, params=params or {}, timeout=self.timeout)
            r.raise_for_status()
            data = r.json()
        except requests.RequestException as e:
            raise BitrixApiError(f"HTTP error calling {method}: {e}") from e
        except ValueError as e:
            raise BitrixApiError(f"Non-JSON response calling {method}") from e

        # Bitrix errors are usually in "error"/"error_description"
        if "error" in data:
            raise BitrixApiError(f"{method} error: {data.get('error')} - {data.get('error_description')}")
        return data

    def get_user_raw(self, user_id: int) -> Dict[str, Any]:
        """
        Returns first matched user object (all fields Bitrix returns by default).
        Uses user.get with filter[ID].
        """
        # user.get returns a list. We filter by ID. :contentReference[oaicite:2]{index=2}
        resp = self._call("user.get", params={"filter[ID]": user_id})
        users = resp.get("result") or []
        if not users:
            raise BitrixApiError(f"User with ID={user_id} not found")
        return users[0]

    def _try_resolve_photo_url(self, personal_photo: Any) -> Optional[str]:
        """
        Best-effort:
        - If it's already a URL string -> return
        - If it's a numeric ID -> try disk.file.get and take DOWNLOAD_URL :contentReference[oaicite:3]{index=3}
        """
        if not personal_photo:
            return None

        # Case 1: URL already
        if isinstance(personal_photo, str) and personal_photo.startswith(("http://", "https://")):
            return personal_photo

        # Case 2: file id (int or numeric string)
        try:
            file_id = int(personal_photo)
        except (TypeError, ValueError):
            return None

        # Attempt disk.file.get (works when photo is stored as Disk file)
        try:
            f = self._call("disk.file.get", params={"id": file_id}).get("result") or {}
            # DOWNLOAD_URL contains auth token and can be used to download. :contentReference[oaicite:4]{index=4}
            return f.get("DOWNLOAD_URL") or f.get("DETAIL_URL") or f.get("SRC")
        except BitrixApiError:
            # Not a Disk file or not accessible
            return None

    def get_user_with_photo(self, user_id: int) -> Dict[str, Any]:
        """
        Returns:
        {
          ...all bitrix fields...,
          "PHOTO_URL": "... or None"
        }
        """
        user = self.get_user_raw(user_id)
        photo_url = self._try_resolve_photo_url(user.get("PERSONAL_PHOTO"))
        # Add normalized convenience fields
        user_out = dict(user)
        user_out["PHOTO_URL"] = photo_url
        user_out["FULL_NAME"] = " ".join(x for x in [user.get("NAME"), user.get("LAST_NAME")] if x)
        return user_out




from typing import Any, Dict, Optional

def pick(deal: Dict[str, Any], key: str, default: Any = None) -> Any:
    """
    Безопасно берёт поле из deal_data.
    """
    v = deal.get(key, default)
    # Битрикс иногда возвращает "" вместо None
    if v == "":
        return default
    return v

def bitrix_checkbox_to_bool(value: Any) -> bool:
    """
    Приводим чекбокс к bool.
    В Битриксе это часто: "Y"/"N", 1/0, True/False, "1"/"0".
    """
    if value in (True, 1, "1", "Y", "y", "true", "True"):
        return True
    return False