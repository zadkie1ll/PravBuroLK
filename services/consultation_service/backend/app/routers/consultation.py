from __future__ import annotations

import logging
import re
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import JSONResponse

from ..config import settings
from ..services import deal_data, report_mapping
from ..services.pdf_render import render_deal_to_pdf
from ..services.signing import BadSignature, Signer

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/consultation", tags=["consultation"])


def _signer() -> Signer:
    return Signer(key=settings.token_secret_key, salt=settings.token_sign_salt)


def _build_token(deal_id: str) -> str:
    return _signer().sign(deal_id)


def _validate_token(deal_id: str, token: str | None) -> bool:
    if not token:
        return False
    try:
        return _signer().unsign(token) == str(deal_id)
    except BadSignature:
        return False


def _require_token(deal_id: str, token: str | None) -> None:
    if not _validate_token(deal_id, token):
        raise HTTPException(status_code=404, detail="Отчёт не найден")


@router.get("/{deal_id}")
def get_report(deal_id: str, token: str | None = None):
    _require_token(deal_id, token)

    try:
        deal = deal_data.get_deal(deal_id)
    except Exception as exc:
        logger.exception("Failed to load deal %s", deal_id)
        raise HTTPException(status_code=502, detail=f"Не удалось загрузить сделку: {exc}") from exc

    manager_user = deal_data.get_manager(deal.get("ASSIGNED_BY_ID"))

    return {
        "dealId": deal_id,
        "fields": report_mapping.deal_to_report_fields(deal),
        "computed": report_mapping.computed_values(deal),
        "manager": report_mapping.manager_to_report(manager_user),
        "links": report_mapping.static_links(),
    }


@router.post("/{deal_id}/save")
def save_report(deal_id: str, token: str | None = None, fields: dict[str, str] = Body(..., embed=True)):
    _require_token(deal_id, token)

    try:
        deal_data.update_deal_fields(deal_id, report_mapping.report_fields_to_bitrix(fields))
    except Exception as exc:
        logger.exception("Failed to save deal fields for %s", deal_id)
        raise HTTPException(status_code=502, detail=f"Не удалось сохранить поля в Bitrix: {exc}") from exc

    try:
        pdf_bytes = render_deal_to_pdf(deal_id, token)

        if settings.debug_pdf_output_path:
            Path(settings.debug_pdf_output_path).write_bytes(pdf_bytes)
            logger.info("Saved debug PDF copy to %s", settings.debug_pdf_output_path)

        deal_data.upload_report_file(
            deal_id,
            settings.field_report_file,
            f"consultation_{deal_id}.pdf",
            pdf_bytes,
        )
    except Exception as exc:
        logger.exception("Failed to render/upload PDF for deal %s", deal_id)
        # Поля уже сохранены в Bitrix — сообщаем отдельно, чтобы не показалось, что
        # пропали и данные тоже.
        raise HTTPException(status_code=502, detail=f"Поля сохранены, но PDF не сформирован: {exc}") from exc

    return {"status": "ok"}


def _extract_deal_id(post_data: dict) -> str | None:
    document_id_2 = post_data.get("document_id[2]")
    if not document_id_2:
        return None
    match = re.search(r"DEAL_(\d+)", document_id_2)
    return match.group(1) if match else None


@router.post("/link")
async def create_report_link(request: Request):
    """Дёргается роботом/автоматизацией Bitrix (как /dogovor у documents_service):
    вычисляет подписанную ссылку на отчёт и кладёт её в поле сделки.
    """
    content_type = (request.headers.get("content-type") or "").lower()
    post_data = dict(await request.json()) if "application/json" in content_type else dict(await request.form())

    deal_id = _extract_deal_id(post_data)
    if not deal_id:
        return JSONResponse({"status": "error", "message": "Invalid deal ID"}, status_code=400)

    token = _build_token(deal_id)
    link = f"{settings.public_base_url}/{deal_id}?token={quote(token)}"

    try:
        deal_data.update_deal_fields(deal_id, {settings.field_report_link: link})
    except Exception as exc:
        logger.exception("Failed to save report link for deal %s", deal_id)
        return JSONResponse({"status": "error", "message": str(exc)}, status_code=502)

    return {"status": "success", "deal_id": deal_id, "link": link}
