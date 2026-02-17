# services/managers_sync.py
from django.db import transaction
from django.utils import timezone
from django.contrib.auth import get_user_model
import secrets
from bitrix.services.bitrix_client import BitrixClient
from leadreport.models import SalesManager, IssuedCredentialLog

BITRIX_WEBHOOK_URL = "https://prav-buro.bitrix24.ru/rest/24/pa1x5irnfpbcnh27/"
SALES_DEPARTMENT_ID = 5  # <-- твой ID отдела продаж

User = get_user_model()


def _make_username(bitrix_user_id: int, email: str) -> str:
    email = (email or "").strip().lower()
    return email if email else f"b24_{bitrix_user_id}"


def _get_or_create_user(bitrix_user_id: int, email: str, full_name: str):
    username = _make_username(bitrix_user_id, email)

    user = User.objects.filter(username=username).first()

    if not user and email:
        user = User.objects.filter(email=email).first()

    created = False
    temp_password = None

    if not user:
        temp_password = secrets.token_urlsafe(9)
        user = User.objects.create_user(
            username=username,
            password=temp_password,
            email=email or "",
        )
        created = True

    # обновим имя (если стандартный User)
    if hasattr(user, "first_name") and hasattr(user, "last_name"):
        parts = (full_name or "").split()
        if parts:
            user.first_name = parts[0]
            user.last_name = " ".join(parts[1:]) if len(parts) > 1 else ""

    user.is_active = True

    # update_fields безопаснее собирать динамически
    fields = ["email", "is_active"]
    if hasattr(user, "first_name"):
        fields += ["first_name", "last_name"]
    user.save(update_fields=list(dict.fromkeys(fields)))

    return user, created, temp_password


def sync_sales_managers_from_bitrix_logic() -> dict:
    b24 = BitrixClient(BITRIX_WEBHOOK_URL)

    users = b24.get_users(
        filter_params={"ACTIVE": True, "UF_DEPARTMENT": SALES_DEPARTMENT_ID},
        select=["ID", "NAME", "LAST_NAME", "EMAIL", "PERSONAL_PHONE", "WORK_PHONE", "ACTIVE", "UF_DEPARTMENT"],
    )

    incoming_ids: set[int] = set()
    created = 0
    updated = 0
    created_django_users = 0

    new_credentials: list[dict] = []

    with transaction.atomic():
        for u in users:
            bitrix_user_id = int(u["ID"])
            incoming_ids.add(bitrix_user_id)

            full_name = f"{(u.get('NAME') or '').strip()} {(u.get('LAST_NAME') or '').strip()}".strip()
            email = (u.get("EMAIL") or "").strip().lower()
            phone = (u.get("WORK_PHONE") or u.get("PERSONAL_PHONE") or "").strip()

            manager_obj, was_created = SalesManager.objects.update_or_create(
                bitrix_user_id=bitrix_user_id,
                defaults={
                    "name": full_name or f"User {bitrix_user_id}",
                    "email": email,
                    "phone": phone,
                    "is_active": True,
                },
            )

            # ✅ создаём/привязываем Django user
            if manager_obj.user_id is None:
                user_obj, user_created, temp_password = _get_or_create_user(
                    bitrix_user_id=bitrix_user_id,
                    email=email,
                    full_name=manager_obj.name,
                )
                manager_obj.user = user_obj
                manager_obj.save(update_fields=["user"])

                if user_created:
                    created_django_users += 1

                    # ✅ ЛОГИРУЕМ В БД ВЫДАННЫЕ КРЕДЫ (username+password)
                    IssuedCredentialLog.objects.create(
                        manager=manager_obj,
                        username=user_obj.username,
                        password=temp_password or "",
                    )

                    new_credentials.append(
                        {"username": user_obj.username, "password": temp_password or "", "manager": manager_obj.name}
                    )

            created += 1 if was_created else 0
            updated += 0 if was_created else 1

        # деактивация тех, кого больше нет в отделе
        deactivated_qs = SalesManager.objects.exclude(bitrix_user_id__in=incoming_ids).filter(is_active=True)
        deactivated_count = deactivated_qs.count()
        deactivated_ids = list(deactivated_qs.values_list("id", flat=True))
        deactivated_qs.update(is_active=False)

        # отключим связанные Django-аккаунты
        User.objects.filter(sales_manager_profile__id__in=deactivated_ids).update(is_active=False)

    return {
        "ok": True,
        "department_id": SALES_DEPARTMENT_ID,
        "total_from_bitrix": len(users),
        "created": created,
        "updated": updated,
        "deactivated": deactivated_count,
        "django_users_created": created_django_users,
        "new_credentials": new_credentials,
        "synced_at": timezone.now().isoformat(),
    }
