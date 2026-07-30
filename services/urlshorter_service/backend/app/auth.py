from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from .config import settings

# Токен всегда выдаёт admin_panel_service (/auth/login) — этот сервис своих staff
# не заводит и не логинит, только принимает готовый JWT из хаба (единый вход).
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="unused", auto_error=False)

credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Не удалось подтвердить учётные данные",
    headers={"WWW-Authenticate": "Bearer"},
)


def require_staff(token: str | None = Depends(oauth2_scheme)) -> dict:
    """Доверяет claim'у is_staff в токене, подписанном общим JWT_SECRET с admin_panel_service —
    без локальной таблицы users, см. services/leadreport_service/backend/app/auth.py:require_staff."""
    if not token:
        raise credentials_exception
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        raise credentials_exception

    if not payload.get("is_staff"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Доступно только сотрудникам")
    return payload
