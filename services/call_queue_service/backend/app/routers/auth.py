from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import create_access_token, get_current_user, hash_password, verify_password
from ..db import get_db
from ..models import User
from ..schemas import LoginRequest, RegisterRequest, TokenResponse
from ..services import leadreport_client
from ..services.leadreport_client import LeadreportClientError

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    """Только для локального прототипа — создание тестового пользователя сервиса."""
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Пользователь с таким email уже существует")

    try:
        sales_manager = leadreport_client.get_by_email(payload.email)
    except LeadreportClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        sales_manager_id=sales_manager.id if sales_manager else None,
        sales_manager_name=sales_manager.name if sales_manager else "",
        sales_manager_megafon_user=sales_manager.megafon_user if sales_manager else "",
        sales_manager_megafon_group=sales_manager.megafon_group if sales_manager else "",
        sales_manager_megafon_clid=sales_manager.megafon_clid if sales_manager else "",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return TokenResponse(access_token=create_access_token(user))


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email или пароль",
        )
    # Обновляем кэш SalesManager при каждом входе, чтобы megafon_user/group/clid не протухали.
    try:
        sales_manager = leadreport_client.get_by_email(user.email)
    except LeadreportClientError:
        sales_manager = None
    if sales_manager:
        user.sales_manager_id = sales_manager.id
        user.sales_manager_name = sales_manager.name
        user.sales_manager_megafon_user = sales_manager.megafon_user
        user.sales_manager_megafon_group = sales_manager.megafon_group
        user.sales_manager_megafon_clid = sales_manager.megafon_clid
        db.commit()
    return TokenResponse(access_token=create_access_token(user))


@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "sales_manager_id": current_user.sales_manager_id,
        "sales_manager_name": current_user.sales_manager_name,
    }
