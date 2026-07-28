from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db
from .models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)

credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Не удалось подтвердить учётные данные",
    headers={"WWW-Authenticate": "Bearer"},
)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)


def create_access_token(user: User) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expires_minutes)
    payload = {"sub": str(user.id), "username": user.username, "is_staff": user.is_staff, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def get_current_user(token: str | None = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    if not token:
        raise credentials_exception
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.get(User, int(user_id))
    if user is None or not user.is_active:
        raise credentials_exception
    return user


def require_staff(token: str | None = Depends(oauth2_scheme)) -> dict:
    """Единый вход из admin_panel_service: доверяет claim'у is_staff в токене, подписанном общим
    JWT_SECRET, без требования локальной строки в users — staff здесь никогда не заводится
    отдельно, весь их логин живёт в admin_panel_service. Обычные (не staff) пользователи
    (менеджеры на /stats/me) по-прежнему логинятся локально через get_current_user."""
    if not token:
        raise credentials_exception
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        raise credentials_exception

    if not payload.get("is_staff"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Доступно только сотрудникам")
    return payload


def check_internal_token(authorization: str | None) -> bool:
    """Общий секрет для сервис-сервис вызовов (аналог leadreport/views.py:_check_internal_token
    в монолите). Если internal_api_token не задан — эндпоинт открыт (локальный прототип)."""
    if not settings.internal_api_token:
        return True
    provided = (authorization or "").removeprefix("Bearer ").strip()
    return provided == settings.internal_api_token
