"""Создать/обновить staff-пользователя admin_panel_service.
Запуск: docker compose exec backend python scripts/create_admin.py <username> <password>
"""
import sys

sys.path.insert(0, "/app")

from app.auth import hash_password
from app.db import SessionLocal
from app.models import User


def main():
    if len(sys.argv) != 3:
        print("Usage: create_admin.py <username> <password>")
        sys.exit(1)

    username, password = sys.argv[1], sys.argv[2]
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if user:
            user.hashed_password = hash_password(password)
            user.is_staff = True
            print(f"Updated existing user {username}")
        else:
            user = User(username=username, hashed_password=hash_password(password), is_staff=True)
            db.add(user)
            print(f"Created staff user {username}")
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
