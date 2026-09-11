"""Создать/обновить staff-пользователя admin_panel_service.
Запуск: docker compose exec backend python scripts/create_admin.py <username> <password> [role]
role: admin (по умолчанию) | director | marketer
"""
import sys

sys.path.insert(0, "/app")

from app.auth import hash_password
from app.db import SessionLocal
from app.models import User

VALID_ROLES = {"admin", "director", "marketer"}


def main():
    if len(sys.argv) not in (3, 4):
        print("Usage: create_admin.py <username> <password> [role: admin|director|marketer]")
        sys.exit(1)

    username, password = sys.argv[1], sys.argv[2]
    role = sys.argv[3] if len(sys.argv) == 4 else "admin"
    if role not in VALID_ROLES:
        print(f"Invalid role {role!r}, must be one of {sorted(VALID_ROLES)}")
        sys.exit(1)

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if user:
            user.hashed_password = hash_password(password)
            user.is_staff = True
            user.role = role
            print(f"Updated existing user {username} (role={role})")
        else:
            user = User(username=username, hashed_password=hash_password(password), is_staff=True, role=role)
            db.add(user)
            print(f"Created staff user {username} (role={role})")
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
