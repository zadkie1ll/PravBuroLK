"""One-shot ETL: копирует clients_client/clients_employee/clients_referralclick/
clients_application из монолита (схема public, Django ORM) в схему referral_stats_service.

owner_content_type/referral_owner_content_type (Django ContentType) сплющиваются в
owner_type/referral_owner_type ('client'|'employee') через django_content_type.model —
без переноса ContentType framework целиком (нужны только 2 конкретных типа).

Explicit-PK insert + ON CONFLICT (id) DO NOTHING — идемпотентно.

Использование:
    SOURCE_DATABASE_URL=postgresql://admin:...@host:5440/bd \
    DATABASE_URL=postgresql://pravburo:pravburo@shared_postgres:5432/pravburo \
    DB_SCHEMA=referral_stats \
    python scripts/etl_import_referral_stats.py
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
    dest_schema = os.environ.get("DB_SCHEMA", "referral_stats")

    src_conn = _connect(source_url)
    dest_conn = _connect(dest_url, schema=dest_schema)

    with src_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as src_cur, dest_conn.cursor() as dest_cur:
        # content_type.id -> 'client'|'employee', остальные типы нам не нужны
        src_cur.execute(
            "select id, model from django_content_type where app_label = 'clients' and model in ('client', 'employee')"
        )
        ct_map = {row["id"]: row["model"] for row in src_cur.fetchall()}

        src_cur.execute("select id, name, surname, middlename, referral_code from clients_client")
        clients = src_cur.fetchall()
        psycopg2.extras.execute_values(
            dest_cur,
            "insert into clients (id, name, surname, middlename, referral_code) values %s on conflict (id) do nothing",
            [(c["id"], c["name"], c["surname"], c["middlename"], c["referral_code"]) for c in clients],
        )
        dest_conn.commit()
        print(f"clients: {len(clients)}")

        src_cur.execute("select id, name, referral_code from clients_employee")
        employees = src_cur.fetchall()
        psycopg2.extras.execute_values(
            dest_cur,
            "insert into employees (id, name, referral_code) values %s on conflict (id) do nothing",
            [(e["id"], e["name"], e["referral_code"]) for e in employees],
        )
        dest_conn.commit()
        print(f"employees: {len(employees)}")

        src_cur.execute("select id, owner_content_type_id, owner_object_id from clients_referralclick")
        clicks = src_cur.fetchall()
        rows = [
            (c["id"], ct_map[c["owner_content_type_id"]], c["owner_object_id"])
            for c in clicks
            if c["owner_content_type_id"] in ct_map and c["owner_object_id"] is not None
        ]
        psycopg2.extras.execute_values(
            dest_cur,
            "insert into referral_clicks (id, owner_type, owner_id) values %s on conflict (id) do nothing",
            rows,
        )
        dest_conn.commit()
        print(f"referral_clicks: {len(rows)} (source had {len(clicks)})")

        src_cur.execute(
            "select id, referral_owner_content_type_id, referral_owner_object_id from clients_application"
        )
        apps = src_cur.fetchall()
        rows = [
            (a["id"], ct_map.get(a["referral_owner_content_type_id"]), a["referral_owner_object_id"])
            for a in apps
        ]
        psycopg2.extras.execute_values(
            dest_cur,
            "insert into applications (id, referral_owner_type, referral_owner_id) values %s on conflict (id) do nothing",
            rows,
        )
        dest_conn.commit()
        print(f"applications: {len(rows)}")

    for table in ["clients", "employees", "referral_clicks", "applications"]:
        _reset_sequence(dest_conn, table)

    src_conn.close()
    dest_conn.close()


if __name__ == "__main__":
    main()
