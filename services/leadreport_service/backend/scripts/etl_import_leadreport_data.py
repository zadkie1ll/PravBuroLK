"""Разовый ETL: переносит данные leadreport-приложения монолита (SalesManager, LeadSource,
LeadEntry, IssuedCredentialLog + связанные Django-пользователи) в схему leadreport_service.

Явные PK-инсерты сохраняют старые id (без ремаппинга), идемпотентно (ON CONFLICT DO NOTHING),
после переноса — setval по каждой последовательности. Django-пароли не переносятся
(несовместимый PBKDF2-хэш) — новым пользователям ставится неиспользуемый плейсхолдер-хэш,
логин продолжает идти через собственный логин/пароль сервиса (реальный вход по email/username,
восстановление доступа — через администратора, как и раньше через IssuedCredentialLog).

Источник: локальная копия прод-снапшота (см. project-microservices-migration память), НЕ прод.
Запуск: docker compose exec backend python scripts/etl_import_leadreport_data.py
"""
import os
import sys

import psycopg2
import psycopg2.extras

sys.path.insert(0, "/app")

SOURCE_DSN = os.getenv(
    "ETL_SOURCE_DSN",
    "postgresql://admin:admin@host.docker.internal:5440/bd",
)
DEST_SCHEMA = "leadreport"


def get_dest_conn():
    from app.config import settings

    return psycopg2.connect(settings.database_url.replace("postgresql+psycopg2", "postgresql"))


def main():
    src = psycopg2.connect(SOURCE_DSN)
    dst = get_dest_conn()
    src_cur = src.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    dst_cur = dst.cursor()
    dst_cur.execute(f"SET search_path TO {DEST_SCHEMA}")

    # --- users (только те auth_user, на кого ссылается leadreport_salesmanager.user_id) ---
    src_cur.execute(
        """
        select au.id, au.username, coalesce(au.email, '') as email, au.is_staff, au.is_superuser, au.is_active
        from auth_user au
        where au.id in (select user_id from leadreport_salesmanager where user_id is not null)
        order by au.id
        """
    )
    users = src_cur.fetchall()
    users_created = 0
    for u in users:
        placeholder_hash = "!imported-" + os.urandom(16).hex()
        is_staff = bool(u["is_staff"] or u["is_superuser"])
        dst_cur.execute(
            """
            insert into users (id, username, email, hashed_password, is_active, is_staff)
            values (%s, %s, %s, %s, %s, %s)
            on conflict (id) do nothing
            """,
            (u["id"], u["username"], u["email"], placeholder_hash, u["is_active"], is_staff),
        )
        users_created += dst_cur.rowcount

    # --- sales_managers ---
    src_cur.execute(
        """
        select id, bitrix_user_id, name, email, phone, megafon_user, megafon_group, megafon_clid,
               user_id, is_active, created_at, updated_at
        from leadreport_salesmanager
        order by id
        """
    )
    managers = src_cur.fetchall()
    managers_created = 0
    for m in managers:
        dst_cur.execute(
            """
            insert into sales_managers
                (id, bitrix_user_id, name, email, phone, megafon_user, megafon_group, megafon_clid,
                 user_id, is_active, created_at, updated_at)
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            on conflict (id) do nothing
            """,
            (
                m["id"], m["bitrix_user_id"], m["name"], m["email"], m["phone"],
                m["megafon_user"], m["megafon_group"], m["megafon_clid"],
                m["user_id"], m["is_active"], m["created_at"], m["updated_at"],
            ),
        )
        managers_created += dst_cur.rowcount

    # --- lead_sources ---
    src_cur.execute("select id, name, bitrix_id, is_active, created_at from leadreport_leadsource order by id")
    sources = src_cur.fetchall()
    sources_created = 0
    for s in sources:
        dst_cur.execute(
            """
            insert into lead_sources (id, name, bitrix_id, is_active, created_at)
            values (%s, %s, %s, %s, %s)
            on conflict (id) do nothing
            """,
            (s["id"], s["name"], s["bitrix_id"], s["is_active"], s["created_at"]),
        )
        sources_created += dst_cur.rowcount

    # --- lead_entries ---
    src_cur.execute(
        "select id, manager_id, occurred_at, source_id, comment, bitrix_lead_id, created_at "
        "from leadreport_leadentry order by id"
    )
    entries = src_cur.fetchall()
    entries_created = 0
    for e in entries:
        dst_cur.execute(
            """
            insert into lead_entries (id, manager_id, occurred_at, source_id, comment, bitrix_lead_id, created_at)
            values (%s, %s, %s, %s, %s, %s, %s)
            on conflict (id) do nothing
            """,
            (
                e["id"], e["manager_id"], e["occurred_at"], e["source_id"],
                e["comment"], e["bitrix_lead_id"], e["created_at"],
            ),
        )
        entries_created += dst_cur.rowcount

    # --- issued_credential_logs ---
    src_cur.execute(
        "select id, manager_id, username, password, issued_at from leadreport_issuedcredentiallog order by id"
    )
    logs = src_cur.fetchall()
    logs_created = 0
    for log in logs:
        dst_cur.execute(
            """
            insert into issued_credential_logs (id, manager_id, username, password, issued_at)
            values (%s, %s, %s, %s, %s)
            on conflict (id) do nothing
            """,
            (log["id"], log["manager_id"], log["username"], log["password"], log["issued_at"]),
        )
        logs_created += dst_cur.rowcount

    # --- setval для всех последовательностей, чтобы будущие autoincrement-инсерты не коллизировали ---
    for table, pk in [
        ("users", "id"),
        ("sales_managers", "id"),
        ("lead_sources", "id"),
        ("lead_entries", "id"),
        ("issued_credential_logs", "id"),
    ]:
        dst_cur.execute(
            f"select setval(pg_get_serial_sequence('{DEST_SCHEMA}.{table}', '{pk}'), "
            f"greatest(coalesce((select max({pk}) from {table}), 1), 1))"
        )

    dst.commit()

    print(f"users: +{users_created} (source rows: {len(users)})")
    print(f"sales_managers: +{managers_created} (source rows: {len(managers)})")
    print(f"lead_sources: +{sources_created} (source rows: {len(sources)})")
    print(f"lead_entries: +{entries_created} (source rows: {len(entries)})")
    print(f"issued_credential_logs: +{logs_created} (source rows: {len(logs)})")

    src_cur.close()
    dst_cur.close()
    src.close()
    dst.close()


if __name__ == "__main__":
    main()
