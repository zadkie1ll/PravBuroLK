from __future__ import annotations

import base64
from typing import Any

from .bitrix_gateway_client import BitrixClient


def get_deal(deal_id: str) -> dict[str, Any]:
    deal = BitrixClient().call("crm.deal.get", {"id": deal_id})
    if not deal:
        raise ValueError(f"Deal {deal_id} not found")
    return deal


def _resolve_photo_url(personal_photo: Any) -> str | None:
    """Порт bitrix/utils.py: BitrixClient.get_user_with_photo из монолита —
    PERSONAL_PHOTO бывает готовым URL или ID файла на Диске.
    """
    if not personal_photo:
        return None
    if isinstance(personal_photo, str) and personal_photo.startswith(("http://", "https://")):
        return personal_photo
    try:
        file_id = int(personal_photo)
    except (TypeError, ValueError):
        return None
    try:
        file_info = BitrixClient().call("disk.file.get", {"id": file_id}) or {}
    except Exception:
        return None
    return file_info.get("DOWNLOAD_URL") or file_info.get("DETAIL_URL") or file_info.get("SRC")


def get_manager(assigned_by_id: str | int | None) -> dict[str, Any]:
    if not assigned_by_id:
        return {}
    users = BitrixClient().call("user.get", {"filter": {"ID": assigned_by_id}}) or []
    user = users[0] if users else {}
    if user:
        user = dict(user)
        user["PHOTO_URL"] = _resolve_photo_url(user.get("PERSONAL_PHOTO"))
    return user


def update_deal_fields(deal_id: str, fields: dict[str, Any]) -> None:
    if not fields:
        return
    BitrixClient().call("crm.deal.update", {"id": deal_id, "fields": fields})


def upload_report_file(deal_id: str, field_id: str, filename: str, pdf_bytes: bytes) -> None:
    encoded = base64.b64encode(pdf_bytes).decode("ascii")
    update_deal_fields(deal_id, {field_id: {"fileData": [filename, encoded]}})
