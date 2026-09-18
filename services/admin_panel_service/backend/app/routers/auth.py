from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from ..auth import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    get_current_user,
    verify_foreign_sso_token,
    verify_password,
)
from ..config import settings
from ..db import get_db
from ..models import User
from ..schemas import LoginRequest, TokenResponse, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE_NAME = "refresh_token"


def _set_refresh_cookie(response: Response, user: User) -> None:
    response.set_cookie(
        REFRESH_COOKIE_NAME,
        create_refresh_token(user),
        max_age=60 * 60 * 24 * settings.refresh_token_expires_days,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/auth",
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    username = payload.username.strip()
    if not username or not payload.password:
        raise HTTPException(status_code=400, detail="username and password required")

    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный логин или пароль")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Пользователь деактивирован")

    _set_refresh_cookie(response, user)
    return TokenResponse(access_token=create_access_token(user), user=UserOut.model_validate(user))


@router.post("/sso-exchange", response_model=TokenResponse)
def sso_exchange(token: str, response: Response, db: Session = Depends(get_db)):
    # Принимает переход из бот-админки (GET /api/auth/sso-to-lk) — та передаёт короткоживущий
    # (2 мин) токен с одним username, без role/is_staff. Меняем его на полноценную здешнюю
    # сессию (обычный access_token + refresh-кука), а не используем чужой токен напрямую —
    # иначе сессия жила бы 2 минуты и не годилась бы для обратной пересылки в бот-админку.
    payload = verify_foreign_sso_token(token)
    username = payload.get("username")
    user = db.query(User).filter(User.username == username).first() if username else None
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Пользователь не найден в LK")

    _set_refresh_cookie(response, user)
    return TokenResponse(access_token=create_access_token(user), user=UserOut.model_validate(user))


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    response: Response,
    db: Session = Depends(get_db),
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE_NAME),
):
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Нет refresh-токена")

    payload = decode_refresh_token(refresh_token)
    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Пользователь недоступен")

    # Скользящее окно — раз воспользовались refresh-токеном, продлеваем его ещё на
    # refresh_token_expires_days от текущего момента, а не от исходного логина.
    _set_refresh_cookie(response, user)
    return TokenResponse(access_token=create_access_token(user), user=UserOut.model_validate(user))


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(REFRESH_COOKIE_NAME, path="/auth")
    return {"detail": "ok"}


@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return {"detail": "ok", "user": UserOut.model_validate(current_user)}
