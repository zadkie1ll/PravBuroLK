from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import create_access_token, get_current_user, hash_password, verify_password
from ..db import get_db
from ..models import Department, User
from ..schemas import DepartmentOut, LoginRequest, RegisterRequest, TokenResponse, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


def _department_codes(user: User) -> list[str]:
    codes = [d.code for d in user.departments if d.is_active]
    legacy_code = str((user.stats or {}).get("department", "")).strip()
    if legacy_code and legacy_code not in codes:
        codes.append(legacy_code)
    return codes


def _department_payload(user: User, db: Session) -> list[DepartmentOut]:
    departments = [DepartmentOut(code=d.code, name=d.name) for d in user.departments if d.is_active]
    known_codes = {d.code for d in departments}
    legacy_code = str((user.stats or {}).get("department", "")).strip()
    if legacy_code and legacy_code not in known_codes:
        legacy = db.query(Department).filter(Department.code == legacy_code, Department.is_active.is_(True)).first()
        if legacy:
            departments.append(DepartmentOut(code=legacy.code, name=legacy.name))
    return departments


def serialize_user(user: User, db: Session) -> UserOut:
    codes = _department_codes(user)
    return UserOut(
        id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        department=codes[0] if codes else "",
        departments=_department_payload(user, db),
        is_staff=user.is_staff,
    )


def _assign_department(user: User, department_code: str, db: Session) -> None:
    stats = dict(user.stats or {})
    stats["department"] = department_code
    user.stats = stats
    department = db.query(Department).filter(Department.code == department_code, Department.is_active.is_(True)).first()
    if department and department not in user.departments:
        user.departments.append(department)


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    username = payload.username.strip()
    if not username or not payload.password or not payload.department:
        raise HTTPException(status_code=400, detail="username, password and department required")

    department = db.query(Department).filter(Department.code == payload.department, Department.is_active.is_(True)).first()
    if not department:
        raise HTTPException(status_code=400, detail="Неизвестный отдел")

    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=409, detail="Пользователь уже существует")

    user = User(username=username, hashed_password=hash_password(payload.password))
    _assign_department(user, payload.department, db)
    db.add(user)
    db.commit()
    db.refresh(user)
    return TokenResponse(access_token=create_access_token(user), user=serialize_user(user, db))


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

    if not _department_codes(user):
        if not payload.department:
            raise HTTPException(status_code=400, detail="Укажите отдел")
        department = db.query(Department).filter(Department.code == payload.department, Department.is_active.is_(True)).first()
        if not department:
            raise HTTPException(status_code=400, detail="Неизвестный отдел")
        _assign_department(user, payload.department, db)
        db.commit()
        db.refresh(user)

    return TokenResponse(access_token=create_access_token(user), user=serialize_user(user, db))


@router.get("/me")
def me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"detail": "ok", "user": serialize_user(current_user, db)}
