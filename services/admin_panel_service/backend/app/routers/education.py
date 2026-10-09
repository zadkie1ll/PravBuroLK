"""Education management gateway; validates live hub permissions on every request."""
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from jose import jwt
from starlette.background import BackgroundTask
from starlette.responses import StreamingResponse

from ..auth import get_current_user
from ..config import settings
from ..models import User

router = APIRouter(prefix="/education-management/hr", tags=["education"])


def require_education_manager(user: User = Depends(get_current_user)) -> User:
    if not user.is_staff or user.role not in {"admin", "director"}:
        raise HTTPException(status_code=403, detail="Нет доступа к управлению обучением")
    return user


@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_education(path: str, request: Request, user: User = Depends(require_education_manager)):
    if any(part in {".", ".."} for part in path.split("/")):
        raise HTTPException(status_code=400, detail="Недопустимый путь")
    signing_secret = settings.education_admin_secret or settings.jwt_secret
    token = jwt.encode({
        "sub": str(user.id), "username": user.username,
        "iss": "admin_panel", "aud": "education-admin", "type": "education_admin",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=2),
    }, signing_secret, algorithm=settings.jwt_algorithm)
    headers = {"Authorization": f"Bearer {token}"}
    if request.headers.get("content-type"):
        headers["Content-Type"] = request.headers["content-type"]
    client = httpx.AsyncClient(timeout=httpx.Timeout(600, connect=10), follow_redirects=False)
    try:
        upstream_request = client.build_request(
            request.method, f"{settings.education_api_url.rstrip('/')}/hr/{path}",
            params=request.query_params, headers=headers, content=request.stream(),
        )
        response = await client.send(upstream_request, stream=True)
    except httpx.HTTPError:
        await client.aclose()
        raise HTTPException(status_code=502, detail="Сервис обучения недоступен")

    async def close():
        await response.aclose()
        await client.aclose()

    return StreamingResponse(
        response.aiter_bytes(), status_code=response.status_code,
        media_type=response.headers.get("content-type", "application/json"),
        background=BackgroundTask(close),
    )
