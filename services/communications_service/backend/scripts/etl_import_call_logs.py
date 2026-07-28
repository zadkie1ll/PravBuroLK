"""One-shot ETL: копирует данные из монолита (communications_* в схеме public, Django ORM)
в схему communications_service.

Простейший случай из трёх ETL в этой миграции: все 3 таблицы совпадают 1-в-1
(CallWebhookEvent/CallProcessingLog/ProcessedCallArchive), нет ссылок на пользователей —
только сам call_processing_logs.event_id -> call_webhook_events.id (переименован из event_id
в Django same name, id сохраняются как есть). Объём заметно больше, чем у call_queue/education
(65к+ строк логов), поэтому вставка идёт пачками через execute_values, а не по одной строке.

Идемпотентно: ON CONFLICT (id) DO NOTHING.

Использование:
    SOURCE_DATABASE_URL=postgresql://admin:...@host:5440/bd \
    DATABASE_URL=postgresql://pravburo:pravburo@shared_postgres:5432/pravburo \
    DB_SCHEMA=communications \
    python scripts/etl_import_call_logs.py
"""
from __future__ import annotations

import os

import psycopg2
import psycopg2.extras

BATCH_SIZE = 5000


def _connect(url: str, schema: str | None = None):
    conn = psycopg2.connect(url)
    if schema:
        with conn.cursor() as cur:
            cur.execute(f"SET search_path TO {schema}")
    return conn


def _bulk_copy(src_cur, dest_conn, select_sql: str, insert_sql: str, row_to_params) -> int:
    src_cur.execute(select_sql)
    total = 0
    with dest_conn.cursor() as dest_cur:
        while True:
            rows = src_cur.fetchmany(BATCH_SIZE)
            if not rows:
                break
            psycopg2.extras.execute_values(
                dest_cur, insert_sql, [row_to_params(r) for r in rows], page_size=BATCH_SIZE
            )
            total += len(rows)
    dest_conn.commit()
    return total


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
    dest_schema = os.environ.get("DB_SCHEMA", "communications")

    # server-side cursor (named) для source — не грузим 65к+65к строк в память разом
    src_conn = _connect(source_url)
    dest_conn = _connect(dest_url, schema=dest_schema)

    with src_conn.cursor(
        name="etl_webhook_events", cursor_factory=psycopg2.extras.RealDictCursor
    ) as src_cur:
        n = _bulk_copy(
            src_cur, dest_conn,
            """select id, created_at, updated_at, event_name, call_id, lead_id, deal_id, contact_id,
                      record_file_id, dedupe_key, status, attempts, raw_payload, audio_file_path,
                      transcript, analysis, error_message
               from communications_callwebhookevent""",
            """insert into call_webhook_events
                   (id, created_at, updated_at, event_name, call_id, lead_id, deal_id, contact_id,
                    record_file_id, dedupe_key, status, attempts, raw_payload, audio_file_path,
                    transcript, analysis, error_message)
               values %s
               on conflict (id) do nothing""",
            lambda r: (
                r["id"], r["created_at"], r["updated_at"], r["event_name"], r["call_id"], r["lead_id"],
                r["deal_id"], r["contact_id"], r["record_file_id"], r["dedupe_key"], r["status"],
                r["attempts"], psycopg2.extras.Json(r["raw_payload"]), r["audio_file_path"],
                psycopg2.extras.Json(r["transcript"]), psycopg2.extras.Json(r["analysis"]), r["error_message"],
            ),
        )
        print(f"call_webhook_events: {n} row(s)")

    with src_conn.cursor(
        name="etl_processing_logs", cursor_factory=psycopg2.extras.RealDictCursor
    ) as src_cur:
        n = _bulk_copy(
            src_cur, dest_conn,
            """select id, created_at, event_id, level, message, details
               from communications_callprocessinglog""",
            """insert into call_processing_logs (id, created_at, event_id, level, message, details)
               values %s
               on conflict (id) do nothing""",
            lambda r: (
                r["id"], r["created_at"], r["event_id"], r["level"], r["message"],
                psycopg2.extras.Json(r["details"]),
            ),
        )
        print(f"call_processing_logs: {n} row(s)")

    with src_conn.cursor(
        name="etl_archive", cursor_factory=psycopg2.extras.RealDictCursor
    ) as src_cur:
        n = _bulk_copy(
            src_cur, dest_conn,
            """select id, created_at, source_event_id, call_id, lead_id, deal_id, contact_id,
                      record_file_id, audio_file_path, transcript, analysis, source_payload
               from communications_processedcallarchive""",
            """insert into processed_call_archive
                   (id, created_at, source_event_id, call_id, lead_id, deal_id, contact_id,
                    record_file_id, audio_file_path, transcript, analysis, source_payload)
               values %s
               on conflict (id) do nothing""",
            lambda r: (
                r["id"], r["created_at"], r["source_event_id"], r["call_id"], r["lead_id"], r["deal_id"],
                r["contact_id"], r["record_file_id"], r["audio_file_path"],
                psycopg2.extras.Json(r["transcript"]), psycopg2.extras.Json(r["analysis"]),
                psycopg2.extras.Json(r["source_payload"]),
            ),
        )
        print(f"processed_call_archive: {n} row(s)")

    for table in ("call_webhook_events", "call_processing_logs", "processed_call_archive"):
        _reset_sequence(dest_conn, table)
    print("Done.")


if __name__ == "__main__":
    main()
