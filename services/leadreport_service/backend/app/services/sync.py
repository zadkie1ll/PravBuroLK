import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import hash_password
from ..config import settings
from ..models import IssuedCredentialLog, LeadSource, SalesManager, User
from .bitrix_client import BitrixClient


def _make_username(bitrix_user_id: int, email: str) -> str:
    email = (email or "").strip().lower()
    return email if email else f"b24_{bitrix_user_id}"


def _get_or_create_user(db: Session, bitrix_user_id: int, email: str) -> tuple[User, bool, str | None]:
    username = _make_username(bitrix_user_id, email)

    user = db.scalar(select(User).where(User.username == username))
    if not user and email:
        user = db.scalar(select(User).where(User.email == email))

    created = False
    temp_password = None

    if not user:
        temp_password = secrets.token_urlsafe(9)
        user = User(username=username, email=email or "", hashed_password=hash_password(temp_password))
        db.add(user)
        db.flush()
        created = True

    user.email = email or user.email
    user.is_active = True
    return user, created, temp_password


def sync_sales_managers_from_bitrix(db: Session) -> dict:
    """Портировано из leadreport/services/managers_sync.py — теперь через bitrix_gateway_service
    вместо собственного захардкоженного BitrixClient(webhook_url)."""
    b24 = BitrixClient()
    users = b24.paginated_call(
        "user.get",
        {"filter": {"ACTIVE": True, "UF_DEPARTMENT": settings.lead_sales_department_id}},
    )

    incoming_ids: set[int] = set()
    created = 0
    updated = 0
    created_django_users = 0
    new_credentials: list[dict] = []

    for u in users:
        bitrix_user_id = int(u["ID"])
        incoming_ids.add(bitrix_user_id)

        full_name = f"{(u.get('NAME') or '').strip()} {(u.get('LAST_NAME') or '').strip()}".strip()
        email = (u.get("EMAIL") or "").strip().lower()
        phone = (u.get("WORK_PHONE") or u.get("PERSONAL_PHONE") or "").strip()

        manager = db.scalar(select(SalesManager).where(SalesManager.bitrix_user_id == bitrix_user_id))
        was_created = manager is None
        if not manager:
            manager = SalesManager(bitrix_user_id=bitrix_user_id)
            db.add(manager)

        manager.name = full_name or f"User {bitrix_user_id}"
        manager.email = email
        manager.phone = phone
        manager.is_active = True
        db.flush()

        if manager.user_id is None:
            user_obj, user_created, temp_password = _get_or_create_user(db, bitrix_user_id, email)
            manager.user_id = user_obj.id
            db.flush()

            if user_created:
                created_django_users += 1
                db.add(IssuedCredentialLog(manager_id=manager.id, username=user_obj.username, password=temp_password or ""))
                new_credentials.append({"username": user_obj.username, "password": temp_password or "", "manager": manager.name})

        created += 1 if was_created else 0
        updated += 0 if was_created else 1

    deactivated_managers = db.scalars(
        select(SalesManager).where(SalesManager.bitrix_user_id.notin_(incoming_ids), SalesManager.is_active.is_(True))
    ).all()
    deactivated_count = len(deactivated_managers)
    deactivated_user_ids = []
    for manager in deactivated_managers:
        manager.is_active = False
        if manager.user_id:
            deactivated_user_ids.append(manager.user_id)

    if deactivated_user_ids:
        db.query(User).filter(User.id.in_(deactivated_user_ids)).update({"is_active": False}, synchronize_session=False)

    db.commit()

    from datetime import timezone as _tz
    from datetime import datetime as _dt

    return {
        "ok": True,
        "total_from_bitrix": len(users),
        "created": created,
        "updated": updated,
        "deactivated": deactivated_count,
        "django_users_created": created_django_users,
        "new_credentials": new_credentials,
        "synced_at": _dt.now(_tz.utc).isoformat(),
    }


def sync_sources_from_bitrix(db: Session) -> dict:
    """Портировано из leadreport/services/sources_sync.py."""
    b24 = BitrixClient()
    items = b24.call("crm.status.list", {"filter": {"ENTITY_ID": "SOURCE"}}) or []

    incoming_ids: set[int] = set()
    created = 0
    updated = 0

    for item in items:
        bitrix_id_raw = item.get("ID")
        if bitrix_id_raw is None:
            continue
        bitrix_id = int(bitrix_id_raw)
        name = (item.get("NAME") or "").strip()
        incoming_ids.add(bitrix_id)

        source = db.scalar(select(LeadSource).where(LeadSource.bitrix_id == bitrix_id))
        if source:
            source.name = name
            source.is_active = True
            updated += 1
        else:
            db.add(LeadSource(bitrix_id=bitrix_id, name=name, is_active=True))
            created += 1

    deactivated = db.scalars(
        select(LeadSource).where(LeadSource.bitrix_id.notin_(incoming_ids), LeadSource.is_active.is_(True))
    ).all()
    for source in deactivated:
        source.is_active = False

    db.commit()

    from datetime import timezone as _tz
    from datetime import datetime as _dt

    return {
        "ok": True,
        "total_from_bitrix": len(items),
        "created": created,
        "updated": updated,
        "deactivated": len(deactivated),
        "synced_at": _dt.now(_tz.utc).isoformat(),
    }
