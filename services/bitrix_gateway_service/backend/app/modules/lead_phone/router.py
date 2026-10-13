import asyncio
import hmac
import json
from urllib.parse import parse_qs

from fastapi import APIRouter, HTTPException, Request

from ...auth import verify_internal_token
from ...config import settings
from fastapi import Depends
from .processor import extract_id

router = APIRouter(tags=["lead-phone"])


@router.post("/webhooks/bitrix24/{secret}", include_in_schema=False)
async def webhook(secret: str, request: Request):
    # URL secret authorizes events; existing internal token still protects /bitrix/*.
    if not settings.lead_phone_enabled:
        raise HTTPException(404, "not_found")
    if not settings.lead_phone_secret or not hmac.compare_digest(secret.encode(), settings.lead_phone_secret.encode()):
        raise HTTPException(403, "forbidden")
    runtime = getattr(request.app.state, "lead_phone", None)
    if runtime is None or not runtime.available:
        raise HTTPException(503, "module_unavailable")
    content_type = request.headers.get("content-type", "").split(";")[0].strip()
    if content_type not in {"application/json", "application/x-www-form-urlencoded"}:
        raise HTTPException(415, "unsupported_content_type")
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > 65536:
            raise HTTPException(413, "too_large")
    try:
        if content_type == "application/json":
            body = json.loads(raw)
        else:
            fields = parse_qs(raw.decode("utf-8"), keep_blank_values=True, max_num_fields=1000)
            if any(len(values) != 1 for values in fields.values()):
                raise ValueError("duplicate_fields")
            body = {key: values[0] for key, values in fields.items()}
    except (ValueError, UnicodeError):
        raise HTTPException(400, "invalid_body") from None
    if not isinstance(body, dict):
        raise HTTPException(400, "invalid_body")
    if body.get("event") != "ONCRMLEADADD":
        return {"status": "ignored"}
    lead_id = extract_id(body)
    if lead_id is None:
        raise HTTPException(400, "invalid_lead_id")
    try:
        added = await asyncio.to_thread(runtime.queue.enqueue, lead_id)
    except Exception:
        raise HTTPException(503, "queue_unavailable") from None
    from fastapi.responses import JSONResponse
    return JSONResponse({"status": "accepted" if added else "duplicate"}, status_code=202)


@router.get("/internal/lead-phone/status", dependencies=[Depends(verify_internal_token)])
async def status(request: Request):
    runtime = getattr(request.app.state, "lead_phone", None)
    result = {"enabled": settings.lead_phone_enabled, "available": bool(runtime and runtime.available),
              "dry_run": settings.lead_phone_dry_run}
    if runtime and runtime.available:
        try:
            result["jobs"] = await asyncio.to_thread(runtime.queue.stats)
        except Exception:
            raise HTTPException(503, "queue_unavailable") from None
    return result
