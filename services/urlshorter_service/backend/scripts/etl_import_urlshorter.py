"""One-shot ETL: копирует urlshorter_urlshortener/urlshorter_click из монолита (схема
public, Django ORM) в url_shorteners/clicks (urlshorter_service).

Explicit-PK insert (id как есть) + ON CONFLICT (id) DO NOTHING — идемпотентно.
Без user-mapping — таблицы не ссылаются на auth_user.

Использование:
    SOURCE_DATABASE_URL=postgresql://admin:...@host:5440/bd \
    DATABASE_URL=postgresql://pravburo:pravburo@shared_postgres:5432/pravburo \
    DB_SCHEMA=urlshorter \
    python scripts/etl_import_urlshorter.py
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
    dest_schema = os.environ.get("DB_SCHEMA", "urlshorter")

    src_conn = _connect(source_url)
    dest_conn = _connect(dest_url, schema=dest_schema)

    with src_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as src_cur:
        src_cur.execute("select id, source, destination, created_at, updated_at from urlshorter_urlshortener")
        shorteners = src_cur.fetchall()

        src_cur.execute("select id, url_id, social, ip_address, user_agent, clicked_at from urlshorter_click")
        clicks = src_cur.fetchall()

    with dest_conn.cursor() as dest_cur:
        for row in shorteners:
            dest_cur.execute(
                """
                insert into url_shorteners (id, source, destination, created_at, updated_at)
                values (%s, %s, %s, %s, %s)
                on conflict (id) do nothing
                """,
                (row["id"], row["source"], row["destination"], row["created_at"], row["updated_at"]),
            )
        print(f"url_shorteners: {len(shorteners)} row(s) processed")

        for row in clicks:
            dest_cur.execute(
                """
                insert into clicks (id, url_id, social, ip_address, user_agent, clicked_at)
                values (%s, %s, %s, %s, %s, %s)
                on conflict (id) do nothing
                """,
                (
                    row["id"],
                    row["url_id"],
                    row["social"],
                    row["ip_address"],
                    row["user_agent"],
                    row["clicked_at"],
                ),
            )
        print(f"clicks: {len(clicks)} row(s) processed")

    dest_conn.commit()
    _reset_sequence(dest_conn, "url_shorteners")
    _reset_sequence(dest_conn, "clicks")
    print("Done.")


if __name__ == "__main__":
    main()
