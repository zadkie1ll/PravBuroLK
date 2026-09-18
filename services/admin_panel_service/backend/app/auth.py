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
    payload = {
        "sub": str(user.id),
        "username": user.username,
        "is_staff": user.is_staff,
        "role": user.role,
        "type": "access",
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(user: User) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expires_days)
    payload = {
        "sub": str(user.id),
        "username": user.username,
        "type": "refresh",
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_refresh_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        raise credentials_exception
    if payload.get("type") != "refresh":
        raise credentials_exception
    return payload


def verify_foreign_sso_token(token: str) -> dict:
    # Токен от внешнего сервиса (сейчас — бот-админка, GET /api/auth/sso-to-lk), подписан
    # тем же общим jwt_secret, но по нашей схеме claim'ов не проходит (нет is_staff/role/type) —
    # используется только на входе в /auth/sso-exchange, не как обычный access-токен.
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        raise credentials_exception


def get_current_user(token: str | None = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    if not token:
        raise credentials_exception
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        user_id = payload.get("sub")
        # Явный "refresh" отбиваем, чтобы refresh-токен из httponly-куки нельзя было
        # подсунуть вместо access-токена в Authorization-заголовке. Токены внешних
        # сервисов (бот-админка) сюда не попадают — они сначала обмениваются на
        # полноценный локальный access_token через POST /auth/sso-exchange.
        if payload.get("type") == "refresh":
            raise credentials_exception
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    try:
        user = db.get(User, int(user_id))
    except (ValueError, TypeError):
        user = None

    if user is None or not user.is_active:
        raise credentials_exception
    return user
