import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from passlib.exc import UnknownHashError
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db
from .models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return pwd_context.verify(password, hashed)
    except (UnknownHashError, ValueError):
        # Плейсхолдер-хэш у пользователей, импортированных ETL из истории звонков
        # ("!imported-" + hex, см. etl_import_call_history.py) — passlib его не опознаёт.
        # Такой пользователь никогда не сможет войти по этому хэшу — это ожидаемо.
        return False


def has_usable_password(hashed: str) -> bool:
    """False для плейсхолдер-хэшей импортированных пользователей — у них ещё не было
    реальной регистрации, значит /auth/register может "забрать" такой аккаунт."""
    try:
        return pwd_context.identify(hashed) is not None
    except (UnknownHashError, ValueError):
        return False


def create_access_token(user: User) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expires_minutes)
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "sales_manager_id": user.sales_manager_id,
        "sales_manager_name": user.sales_manager_name,
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def _hash_refresh_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


def create_refresh_token(user: User, db: Session) -> str:
    """Непрозрачный токен (не JWT) — выдаётся вместе с access-токеном, чтобы фронт мог
    молча перевыпустить access, когда тот истечёт, без повторного ввода логина/пароля."""
    raw_token = secrets.token_urlsafe(48)
    user.refresh_token_hash = _hash_refresh_token(raw_token)
    user.refresh_token_expires_at = datetime.now(timezone.utc) + timedelta(
        days=settings.refresh_token_expires_days
    )
    db.add(user)
    db.commit()
    return raw_token


def verify_refresh_token(raw_token: str, db: Session) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Refresh-токен недействителен, нужен повторный вход",
    )
    token_hash = _hash_refresh_token(raw_token)
    user = db.query(User).filter(User.refresh_token_hash == token_hash).first()
    if user is None or not user.refresh_token_hash:
        raise credentials_exception
    expires_at = user.refresh_token_expires_at
    if expires_at is None:
        raise credentials_exception
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise credentials_exception
    if not user.is_active:
        raise credentials_exception
    return user


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Не удалось подтвердить учётные данные",
        headers={"WWW-Authenticate": "Bearer"},
    )
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
