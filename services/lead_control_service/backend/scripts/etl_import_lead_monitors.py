"""One-shot ETL: копирует lead_control_leadmonitor (монолит, схема public, Django ORM)
в lead_monitors (lead_control_service, своя схема).

Без user-mapping: таблица не ссылается на auth_user (bitrix_deal_id/responsible_bitrix_user_id/
moderator_bitrix_user_id — это ID в Bitrix24, не в Django). ID сохраняются как есть.

Идемпотентно: ON CONFLICT (id) DO NOTHING, повторный запуск не создаёт дублей.

Использование:
    SOURCE_DATABASE_URL=postgresql://admin:...@host:5440/bd \
    DATABASE_URL=postgresql://pravburo:pravburo@shared_postgres:5432/pravburo \
    DB_SCHEMA=lead_control \
    python scripts/etl_import_lead_monitors.py
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


def _reset_sequence(dest_cur, table: str, id_column: str = "id") -> None:
    dest_cur.execute(
        f"select setval(pg_get_serial_sequence(%s, %s), coalesce((select max({id_column}) from {table}), 1), "
        f"(select max({id_column}) from {table}) is not null)",
        (table, id_column),
    )


def main() -> None:
    source_url = os.environ["SOURCE_DATABASE_URL"]
    dest_url = os.environ.get("DATABASE_URL", "postgresql://pravburo:pravburo@shared_postgres:5432/pravburo")
    dest_schema = os.environ.get("DB_SCHEMA", "lead_control")

    src_conn = _connect(source_url)
    dest_conn = _connect(dest_url, schema=dest_schema)

    with src_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as src_cur:
        src_cur.execute(
            """
            select id, bitrix_deal_id, initial_bitrix_task_id, bitrix_task_id,
                   moderator_bitrix_user_id, responsible_bitrix_user_id, task_description,
                   initial_task_created, attempts_total, attempts_today, attempts_last_reset_date,
                   entered_logic_at, current_stage_id, is_active, status, status_comment,
                   last_task_closed_at, last_moderator_task_created_at, last_moderator_task_id,
                   last_checked_at, raw_deal_data, created_at, updated_at
            from lead_control_leadmonitor
            """
        )
        rows = src_cur.fetchall()

    with dest_conn.cursor() as dest_cur:
        for row in rows:
            dest_cur.execute(
                """
                insert into lead_monitors
                    (id, bitrix_deal_id, initial_bitrix_task_id, bitrix_task_id,
                     moderator_bitrix_user_id, responsible_bitrix_user_id, task_description,
                     initial_task_created, attempts_total, attempts_today, attempts_last_reset_date,
                     entered_logic_at, current_stage_id, is_active, status, status_comment,
                     last_task_closed_at, last_moderator_task_created_at, last_moderator_task_id,
                     last_checked_at, raw_deal_data, created_at, updated_at)
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                on conflict (id) do nothing
                """,
                (
                    row["id"],
                    row["bitrix_deal_id"],
                    row["initial_bitrix_task_id"],
                    row["bitrix_task_id"],
                    row["moderator_bitrix_user_id"],
                    row["responsible_bitrix_user_id"],
                    row["task_description"],
                    row["initial_task_created"],
                    row["attempts_total"],
                    row["attempts_today"],
                    row["attempts_last_reset_date"],
                    row["entered_logic_at"],
                    row["current_stage_id"],
                    row["is_active"],
                    row["status"],
                    row["status_comment"],
                    row["last_task_closed_at"],
                    row["last_moderator_task_created_at"],
                    row["last_moderator_task_id"],
                    row["last_checked_at"],
                    psycopg2.extras.Json(row["raw_deal_data"]),
                    row["created_at"],
                    row["updated_at"],
                ),
            )
        print(f"lead_monitors: {len(rows)} row(s) processed")

        _reset_sequence(dest_cur, "lead_monitors")

    dest_conn.commit()
    print("Done.")


if __name__ == "__main__":
    main()
