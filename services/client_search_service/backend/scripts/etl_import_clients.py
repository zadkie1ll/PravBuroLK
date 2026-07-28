"""One-shot ETL: копирует clients_stagetemplate/clients_client из монолита (схема public,
Django ORM) в схему client_search_service. Только поля, нужные для поиска/списка (см.
app/models.py) — договор/платежи/эквайринг остаются в монолите вместе с client_admin_view.

Explicit-PK insert (сохраняем id как есть, чтобы monolith_client_admin_url/<id>/ продолжал
указывать на верного клиента) + ON CONFLICT (id) DO NOTHING — идемпотентно, безопасно
перезапускать. Никакого сопоставления пользователей не нужно: тут нет auth_user FK.

Использование:
    SOURCE_DATABASE_URL=postgresql://admin:...@host:5440/bd \
    DATABASE_URL=postgresql://pravburo:pravburo@shared_postgres:5432/pravburo \
    DB_SCHEMA=client_search \
    python scripts/etl_import_clients.py
"""
from __future__ import annotations

import os

import psycopg2
import psycopg2.extras


def _connect(url: str, schema: str | None = None):
    conn = psycopg2.connect(url)
    if schema:
        with conn.cursor() as cur:
            cur.execute(f"SET search_path TO {schema}")
    return conn


def _reset_sequence(dest_conn, table: str, id_column: str = "id") -> None:
    with dest_conn.cursor() as dest_cur:
        dest_cur.execute(
            f"select setval(pg_get_serial_sequence(%s, %s), coalesce((select max({id_column}) from {table}), 1), "
            f"(select max({id_column}) from {table}) is not null)",
            (table, id_column),
        )
    dest_conn.commit()


def main() -> None:
    source_url = os.environ["SOURCE_DATABASE_URL"]
    dest_url = os.environ.get("DATABASE_URL", "postgresql://pravburo:pravburo@shared_postgres:5432/pravburo")
    dest_schema = os.environ.get("DB_SCHEMA", "client_search")

    src_conn = _connect(source_url)
    dest_conn = _connect(dest_url, schema=dest_schema)

    with src_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as src_cur, dest_conn.cursor() as dest_cur:
        src_cur.execute("select id, name from clients_stagetemplate")
        stages = src_cur.fetchall()
        psycopg2.extras.execute_values(
            dest_cur,
            "insert into stage_templates (id, name) values %s on conflict (id) do nothing",
            [(s["id"], s["name"]) for s in stages],
        )
        dest_conn.commit()
        print(f"stage_templates: {len(stages)}")

        src_cur.execute(
            'select id, name, surname, middlename, bitrix_id, stage_id, "isBlocked" as is_blocked '
            "from clients_client"
        )
        clients = src_cur.fetchall()
        psycopg2.extras.execute_values(
            dest_cur,
            """insert into clients (id, name, surname, middlename, bitrix_id, stage_id, is_blocked)
               values %s on conflict (id) do nothing""",
            [
                (
                    c["id"],
                    c["name"],
                    c["surname"],
                    c["middlename"],
                    c["bitrix_id"],
                    c["stage_id"],
                    bool(c["is_blocked"]),
                )
                for c in clients
            ],
        )
        dest_conn.commit()
        print(f"clients: {len(clients)}")

    _reset_sequence(dest_conn, "stage_templates")
    _reset_sequence(dest_conn, "clients")

    src_conn.close()
    dest_conn.close()


if __name__ == "__main__":
    main()
