"""One-shot ETL: расплющивает clients_dashboardvisit.visits (JSON-массив ISO-таймстемпов на
запись владелец+IP) в одну строку на визит в схеме referral_stats_service. Не идемпотентно
по PK (у визитов в источнике нет собственного id) — вместо этого при повторном запуске сперва
чистит таблицу целиком и заливает заново, что безопасно, т.к. это чисто производная витрина.

Использование:
    SOURCE_DATABASE_URL=postgresql://admin:...@host:5440/bd \
    DATABASE_URL=postgresql://pravburo:pravburo@shared_postgres:5432/pravburo \
    DB_SCHEMA=referral_stats \
    python scripts/etl_import_visit_events.py
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


def main() -> None:
    source_url = os.environ["SOURCE_DATABASE_URL"]
    dest_url = os.environ.get("DATABASE_URL", "postgresql://pravburo:pravburo@shared_postgres:5432/pravburo")
    dest_schema = os.environ.get("DB_SCHEMA", "referral_stats")

    src_conn = _connect(source_url)
    dest_conn = _connect(dest_url, schema=dest_schema)

    with src_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as src_cur:
        src_cur.execute("select visits from clients_dashboardvisit")
        rows = src_cur.fetchall()

    timestamps: list[tuple[str]] = []
    for row in rows:
        for ts in row["visits"] or []:
            timestamps.append((ts,))

    with dest_conn.cursor() as dest_cur:
        dest_cur.execute("truncate table visit_events restart identity")
        psycopg2.extras.execute_values(
            dest_cur, "insert into visit_events (visited_at) values %s", timestamps
        )
    dest_conn.commit()
    print(f"visit_events: {len(timestamps)} (from {len(rows)} dashboard_visit records)")

    src_conn.close()
    dest_conn.close()


if __name__ == "__main__":
    main()
