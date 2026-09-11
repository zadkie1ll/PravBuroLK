"""One-shot ETL: копирует UTM-разметку (urlshorter_utmsource/urlshorter_utmmedium/
urlshorter_botblock/urlshorter_marketinglink/urlshorter_marketingclick) из монолита
(схема public, Django ORM) в utm_sources/utm_mediums/bot_blocks/marketing_links/
marketing_clicks (urlshorter_service). Отдельная фича от UrlShortener/Click,
см. etl_import_urlshorter.py — та таблицы не трогает.

Explicit-PK insert + ON CONFLICT (id) DO UPDATE по мутируемым полям (is_active,
destination и т.п.) — идемпотентно, безопасно перезапускать.

Использование:
    SOURCE_DATABASE_URL=postgresql://admin:...@host:5440/bd \
    DATABASE_URL=postgresql://pravburo:pravburo@shared_postgres:5432/pravburo \
    DB_SCHEMA=urlshorter \
    python scripts/etl_import_marketing_links.py
"""
from __future__ import annotations

import os

import psycopg2
import psycopg2.extras


def _connect(url: str, schema: str | None = None):
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
    dest_schema = os.environ.get("DB_SCHEMA", "urlshorter")

    src_conn = _connect(source_url)
    dest_conn = _connect(dest_url, schema=dest_schema)

    with src_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as src_cur, dest_conn.cursor() as dest_cur:
        src_cur.execute("select id, code, is_active from urlshorter_utmsource")
        rows = src_cur.fetchall()
        psycopg2.extras.execute_values(
            dest_cur,
            """insert into utm_sources (id, code, is_active) values %s
               on conflict (id) do update set code = excluded.code, is_active = excluded.is_active""",
            [(r["id"], r["code"], r["is_active"]) for r in rows],
        )
        dest_conn.commit()
        print(f"utm_sources: {len(rows)} row(s)")

        src_cur.execute("select id, code, is_active from urlshorter_utmmedium")
        rows = src_cur.fetchall()
        psycopg2.extras.execute_values(
            dest_cur,
            """insert into utm_mediums (id, code, is_active) values %s
               on conflict (id) do update set code = excluded.code, is_active = excluded.is_active""",
            [(r["id"], r["code"], r["is_active"]) for r in rows],
        )
        dest_conn.commit()
        print(f"utm_mediums: {len(rows)} row(s)")

        src_cur.execute("select id, key, title, is_active from urlshorter_botblock")
        rows = src_cur.fetchall()
        psycopg2.extras.execute_values(
            dest_cur,
            """insert into bot_blocks (id, key, title, is_active) values %s
               on conflict (id) do update set
                   key = excluded.key, title = excluded.title, is_active = excluded.is_active""",
            [(r["id"], r["key"], r["title"], r["is_active"]) for r in rows],
        )
        dest_conn.commit()
        print(f"bot_blocks: {len(rows)} row(s)")

        src_cur.execute(
            """select id, source, link_type, destination, utm_source_id, utm_medium_id,
                      utm_campaign, utm_content, utm_term, bot_block_id, created_at, updated_at
               from urlshorter_marketinglink"""
        )
        rows = src_cur.fetchall()
        psycopg2.extras.execute_values(
            dest_cur,
            """insert into marketing_links
                   (id, source, link_type, destination, utm_source_id, utm_medium_id,
                    utm_campaign, utm_content, utm_term, bot_block_id, created_at, updated_at)
               values %s
               on conflict (id) do update set
                   destination = excluded.destination,
                   utm_source_id = excluded.utm_source_id,
                   utm_medium_id = excluded.utm_medium_id,
                   utm_campaign = excluded.utm_campaign,
                   utm_content = excluded.utm_content,
                   utm_term = excluded.utm_term,
                   bot_block_id = excluded.bot_block_id,
                   updated_at = excluded.updated_at""",
            [
                (
                    r["id"], r["source"], r["link_type"], r["destination"], r["utm_source_id"],
                    r["utm_medium_id"], r["utm_campaign"], r["utm_content"], r["utm_term"],
                    r["bot_block_id"], r["created_at"], r["updated_at"],
                )
                for r in rows
            ],
        )
        dest_conn.commit()
        print(f"marketing_links: {len(rows)} row(s)")

        src_cur.execute(
            "select id, link_id, ip_address, user_agent, is_bot_preview, clicked_at from urlshorter_marketingclick"
        )
        rows = src_cur.fetchall()
        psycopg2.extras.execute_values(
            dest_cur,
            """insert into marketing_clicks (id, link_id, ip_address, user_agent, is_bot_preview, clicked_at)
               values %s on conflict (id) do nothing""",
            [
                (r["id"], r["link_id"], r["ip_address"], r["user_agent"], r["is_bot_preview"], r["clicked_at"])
                for r in rows
            ],
        )
        dest_conn.commit()
        print(f"marketing_clicks: {len(rows)} row(s)")

    for table in ("utm_sources", "utm_mediums", "bot_blocks", "marketing_links", "marketing_clicks"):
        _reset_sequence(dest_conn, table)

    src_conn.close()
    dest_conn.close()


if __name__ == "__main__":
    main()
