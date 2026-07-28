from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import create_access_token, get_current_user, verify_password
from ..db import get_db
from ..models import SalesManager, User
from ..schemas import LoginRequest, TokenResponse, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


def serialize_user(user: User, db: Session) -> UserOut:
    manager = db.query(SalesManager).filter(SalesManager.user_id == user.id).first()
    return UserOut(
        id=user.id,
        username=user.username,
        is_staff=user.is_staff,
        sales_manager_id=manager.id if manager else None,
        sales_manager_name=manager.name if manager else "",
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    username = payload.username.strip()
    if not username or not payload.password:
        raise HTTPException(status_code=400, detail="username and password required")

    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный логин или пароль")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Пользователь деактивирован")

    return TokenResponse(access_token=create_access_token(user), user=serialize_user(user, db))


@router.get("/me")
def me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"detail": "ok", "user": serialize_user(current_user, db)}
