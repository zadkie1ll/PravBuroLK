from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from ..auth import verify_internal_token
from ..config import settings
from ..services.client import BitrixAPIError, BitrixProfileClient

router = APIRouter(prefix="/bitrix", tags=["bitrix"], dependencies=[Depends(verify_internal_token)])


def _get_client(profile: str) -> BitrixProfileClient:
    webhook_url = settings.profile_webhook_urls.get(profile)
    if not webhook_url:
        raise HTTPException(status_code=400, detail=f"unknown or unconfigured bitrix profile: {profile}")
    return BitrixProfileClient(webhook_url)


def _call_or_502(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except BitrixAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/call")
def call(body: dict[str, Any]):
    client = _get_client(body.get("profile", "default"))
    result = _call_or_502(client.call, body["method"], body.get("params"))
    return {"result": result}


@router.post("/call-with-total")
def call_with_total(body: dict[str, Any]):
    client = _get_client(body.get("profile", "default"))
    items, total = _call_or_502(client.call_with_total, body["method"], body.get("params"))
    return {"items": items, "total": total}


@router.post("/batch-call")
def batch_call(body: dict[str, Any]):
    client = _get_client(body.get("profile", "default"))
    commands = [(cmd["method"], cmd.get("params")) for cmd in body.get("commands", [])]
    pages = _call_or_502(client.batch_call, commands)
    return {"pages": pages}


@router.post("/paginated-call")
def paginated_call(body: dict[str, Any]):
    client = _get_client(body.get("profile", "default"))
    items = _call_or_502(client.paginated_call, body["method"], body.get("params"))
    return {"items": items}
