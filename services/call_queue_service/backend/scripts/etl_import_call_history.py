"""One-shot ETL: копирует историю обзвона из монолита (call_queue_* в схеме public,
Django ORM) в схему call_queue_service (call_sessions/call_queue_items/call_attempts/
bitrix_sync_logs).

Нужно, потому что новый сервис не хранит эту историю как таблицы (см. UserQueueState
в app/models.py) — при переносе существующих данных для неё специально добавлены
таблицы-аналоги (миграция 0003), не используемые обычной работой сервиса.

Идемпотентно: повторный запуск не создаёт дублей (ON CONFLICT DO NOTHING по PK,
пользователи ищутся/создаются по email). ID сессий/элементов/попыток сохраняются как есть,
чтобы не потерять связи (call_queue_items.session_id и т.д.).

Использование:
    SOURCE_DATABASE_URL=postgresql://admin:...@host:5440/bd \
    DATABASE_URL=postgresql://pravburo:pravburo@shared_postgres:5432/pravburo \
    DB_SCHEMA=call_queue \
    python scripts/etl_import_call_history.py
"""
from __future__ import annotations

import os
import secrets

import psycopg2
import psycopg2.extras


def _connect(url: str, schema: str | None = None):
    # psycopg2.connect() не понимает SQLAlchemy-диалект в схеме URL (postgresql+psycopg2://),
    # а .env хранит DATABASE_URL именно в этом формате (для приложения, там это SQLAlchemy).
    conn = psycopg2.connect(url.replace("postgresql+psycopg2://", "postgresql://", 1))
    if schema:
        with conn.cursor() as cur:
            cur.execute(f"SET search_path TO {schema}")
    return conn


def _placeholder_password_hash() -> str:
    # bcrypt-совместимый мусорный хэш — реальный логин через него невозможен, пароли Django
    # (PBKDF2) в принципе не переносимы в bcrypt-схему этого сервиса. Кто из этих людей
    # реально работает с сервисом, зарегистрируется/сбросит пароль как обычно.
    return "!imported-" + secrets.token_hex(16)


def _load_user_map(src_cur, dest_conn, user_ids: set[int]) -> dict[int, int]:
    if not user_ids:
        return {}

    src_cur.execute(
        "select id, username, email from auth_user where id = any(%s)",
        (list(user_ids),),
    )
    django_users = {row["id"]: row for row in src_cur.fetchall()}

    mapping: dict[int, int] = {}
    with dest_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as dest_cur:
        for django_id in user_ids:
            row = django_users.get(django_id)
            email = (row["email"] if row else "") or f"django-user-{django_id}@import.local"

            dest_cur.execute("select id from users where email = %s", (email,))
            existing = dest_cur.fetchone()
            if existing:
                mapping[django_id] = existing["id"]
                continue

            dest_cur.execute(
                """
                insert into users (email, hashed_password, is_active, sales_manager_name)
                values (%s, %s, true, %s)
                returning id
                """,
                (email, _placeholder_password_hash(), (row["username"] if row else "") or ""),
            )
            mapping[django_id] = dest_cur.fetchone()["id"]

    dest_conn.commit()
    return mapping


def _reset_sequence(dest_cur, table: str, id_column: str = "id") -> None:
    dest_cur.execute(
        f"select setval(pg_get_serial_sequence(%s, %s), coalesce((select max({id_column}) from {table}), 1), "
        f"(select max({id_column}) from {table}) is not null)",
        (table, id_column),
    )


def main() -> None:
    source_url = os.environ["SOURCE_DATABASE_URL"]
    dest_url = os.environ.get("DATABASE_URL", "postgresql://pravburo:pravburo@shared_postgres:5432/pravburo")
    dest_schema = os.environ.get("DB_SCHEMA", "call_queue")

    src_conn = _connect(source_url)
    dest_conn = _connect(dest_url, schema=dest_schema)

    with src_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as src_cur:
        src_cur.execute("select id, created_by_id from call_queue_callsession")
        sessions = src_cur.fetchall()

        src_cur.execute("select id, session_id, assigned_to_id from call_queue_callqueueitem")
        items = src_cur.fetchall()

        src_cur.execute("select id, queue_item_id, manager_id from call_queue_callattempt")
        attempts = src_cur.fetchall()

        referenced_user_ids = {row["created_by_id"] for row in sessions}
        referenced_user_ids |= {row["assigned_to_id"] for row in items if row["assigned_to_id"]}
        referenced_user_ids |= {row["manager_id"] for row in attempts}

        user_map = _load_user_map(src_cur, dest_conn, referenced_user_ids)
        print(f"User map: {len(user_map)} django user(s) resolved/created")

        with dest_conn.cursor() as dest_cur:
            src_cur.execute(
                """
                select id, created_by_id, entity_type, date_from, date_to, status, filters_json,
                       total_items, processed_items, success_count, failed_count, created_at, updated_at
                from call_queue_callsession
                """
            )
            rows = src_cur.fetchall()
            for row in rows:
                dest_cur.execute(
                    """
                    insert into call_sessions
                        (id, created_by_id, entity_type, date_from, date_to, status, filters_json,
                         total_items, processed_items, success_count, failed_count, created_at, updated_at)
                    values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    on conflict (id) do nothing
                    """,
                    (
                        row["id"],
                        user_map[row["created_by_id"]],
                        row["entity_type"],
                        row["date_from"],
                        row["date_to"],
                        row["status"],
                        psycopg2.extras.Json(row["filters_json"]),
                        row["total_items"],
                        row["processed_items"],
                        row["success_count"],
                        row["failed_count"],
                        row["created_at"],
                        row["updated_at"],
                    ),
                )
            print(f"call_sessions: {len(rows)} row(s) processed")

            src_cur.execute(
                """
                select id, session_id, entity_type, bitrix_entity_id, bitrix_contact_id, client_name, phone,
                       lead_created_at, source_id, source_name, stage_id, stage_name, responsible_id,
                       responsible_name, status, assigned_to_id, locked_at, attempts_count, last_call_result,
                       last_call_at, last_provider_call_id, bitrix_url, needs_manual_processing,
                       repeat_unanswered, created_at, updated_at
                from call_queue_callqueueitem
                """
            )
            rows = src_cur.fetchall()
            for row in rows:
                dest_cur.execute(
                    """
                    insert into call_queue_items
                        (id, session_id, entity_type, bitrix_entity_id, bitrix_contact_id, client_name, phone,
                         lead_created_at, source_id, source_name, stage_id, stage_name, responsible_id,
                         responsible_name, status, assigned_to_id, locked_at, attempts_count, last_call_result,
                         last_call_at, last_provider_call_id, bitrix_url, needs_manual_processing,
                         repeat_unanswered, created_at, updated_at)
                    values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    on conflict (id) do nothing
                    """,
                    (
                        row["id"],
                        row["session_id"],
                        row["entity_type"],
                        row["bitrix_entity_id"],
                        row["bitrix_contact_id"],
                        row["client_name"],
                        row["phone"],
                        row["lead_created_at"],
                        row["source_id"],
                        row["source_name"],
                        row["stage_id"],
                        row["stage_name"],
                        row["responsible_id"],
                        row["responsible_name"],
                        row["status"],
                        user_map.get(row["assigned_to_id"]) if row["assigned_to_id"] else None,
                        row["locked_at"],
                        row["attempts_count"],
                        row["last_call_result"],
                        row["last_call_at"],
                        row["last_provider_call_id"],
                        row["bitrix_url"],
                        row["needs_manual_processing"],
                        row["repeat_unanswered"],
                        row["created_at"],
                        row["updated_at"],
                    ),
                )
            print(f"call_queue_items: {len(rows)} row(s) processed")

            src_cur.execute(
                """
                select id, queue_item_id, manager_id, started_at, finished_at, result, comment,
                       provider_call_id, created_at
                from call_queue_callattempt
                """
            )
            rows = src_cur.fetchall()
            for row in rows:
                dest_cur.execute(
                    """
                    insert into call_attempts
                        (id, queue_item_id, manager_id, started_at, finished_at, result, comment,
                         provider_call_id, created_at)
                    values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    on conflict (id) do nothing
                    """,
                    (
                        row["id"],
                        row["queue_item_id"],
                        user_map[row["manager_id"]],
                        row["started_at"],
                        row["finished_at"],
                        row["result"],
                        row["comment"],
                        row["provider_call_id"],
                        row["created_at"],
                    ),
                )
            print(f"call_attempts: {len(rows)} row(s) processed")

            src_cur.execute(
                """
                select id, entity_type, entity_id, action, request_payload, response_payload, success,
                       error_text, created_at
                from call_queue_bitrixsynclog
                """
            )
            rows = src_cur.fetchall()
            for row in rows:
                dest_cur.execute(
                    """
                    insert into bitrix_sync_logs
                        (id, entity_type, entity_id, action, request_payload, response_payload, success,
                         error_text, created_at)
                    values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    on conflict (id) do nothing
                    """,
                    (
                        row["id"],
                        row["entity_type"],
                        row["entity_id"],
                        row["action"],
                        psycopg2.extras.Json(row["request_payload"]),
                        psycopg2.extras.Json(row["response_payload"]),
                        row["success"],
                        row["error_text"],
                        row["created_at"],
                    ),
                )
            print(f"bitrix_sync_logs: {len(rows)} row(s) processed")

            for table in ("call_sessions", "call_queue_items", "call_attempts", "bitrix_sync_logs", "users"):
                _reset_sequence(dest_cur, table)

        dest_conn.commit()
    print("Done.")


if __name__ == "__main__":
    main()
