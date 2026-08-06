"""One-shot ETL: копирует client_withdrawals_clientwithdrawalrecord из монолита (схема
public, Django ORM) в withdrawal_records (client_search_service).

Explicit-PK insert (id как есть) + ON CONFLICT (id) DO NOTHING — идемпотентно.
Без user-mapping — таблица ссылается только на clients.id (уже перенесённый
etl_import_clients.py), не на auth_user.

Использование:
    SOURCE_DATABASE_URL=postgresql://admin:...@host:5440/bd \
    DATABASE_URL=postgresql://pravburo:pravburo@shared_postgres:5432/pravburo \
    DB_SCHEMA=client_search \
    python scripts/etl_import_withdrawals.py
"""
from __future__ import annotations

import os

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

    with src_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as src_cur:
        src_cur.execute(
            """
            select id, client_id, withdrawal_date, transfer_date, withdrawal_amount,
                   transferred_amount, tail_amount, comment, created_at, updated_at
            from client_withdrawals_clientwithdrawalrecord
            """
        )
        rows = src_cur.fetchall()

    with dest_conn.cursor() as dest_cur:
        for row in rows:
            dest_cur.execute(
                """
                insert into withdrawal_records
                    (id, client_id, withdrawal_date, transfer_date, withdrawal_amount,
                     transferred_amount, tail_amount, comment, created_at, updated_at)
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                on conflict (id) do nothing
                """,
                (
                    row["id"],
                    row["client_id"],
                    row["withdrawal_date"],
                    row["transfer_date"],
                    row["withdrawal_amount"],
                    row["transferred_amount"],
                    row["tail_amount"],
                    row["comment"],
                    row["created_at"],
                    row["updated_at"],
                ),
            )
        print(f"withdrawal_records: {len(rows)} row(s) processed")

    dest_conn.commit()
    _reset_sequence(dest_conn, "withdrawal_records")
    print("Done.")


if __name__ == "__main__":
    main()
