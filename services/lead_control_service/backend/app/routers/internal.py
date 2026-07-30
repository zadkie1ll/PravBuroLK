from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from ..auth import verify_internal_token
from ..config import settings
from ..services import bitrix_lead_control as bitrix
from ..services.bitrix_gateway_client import BitrixAPIError

router = APIRouter(
    prefix="/api/internal",
    tags=["internal"],
    dependencies=[Depends(verify_internal_token)],
)


@router.post("/duplicate-deal")
def duplicate_deal(body: dict[str, Any]):
    """Заменяет clients/views.py: прямой импорт duplicate_deal_to_agents_category —
    теперь это единственная связь между clients (монолит) и lead_control_service, вместо
    прямого Python-импорта одного Django-приложения в другое."""
    deal_data = body.get("deal_data")
    if not isinstance(deal_data, dict):
        raise HTTPException(status_code=400, detail="deal_data (object) is required")

    try:
        new_deal_id = bitrix.duplicate_deal_to_agents_category(
            deal_data,
            source_category_id=settings.deal_duplication_source_category_id,
            source_won_stage_id=settings.deal_duplication_source_won_stage_id,
            target_category_id=settings.deal_duplication_target_category_id,
            target_first_stage_id=settings.deal_duplication_target_first_stage_id,
        )
    except BitrixAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {"new_deal_id": new_deal_id}
