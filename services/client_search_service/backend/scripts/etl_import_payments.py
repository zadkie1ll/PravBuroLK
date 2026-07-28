"""One-shot ETL: копирует payments_contract/payments_installmentplan/payments_installmentpayment/
payments_actualpayment/payments_otherpayment из монолита (схема public, Django ORM) в схему
client_search_service. Только поля, которые реально показывает client_payments_page.html
(см. app/models.py) — PaymentApplication/amount_paid из монолита эта страница не использует.

Explicit-PK insert (id как есть) + ON CONFLICT (id) DO NOTHING — идемпотентно.
Порядок важен из-за FK: stage_templates/clients уже должны быть перенесены
(etl_import_clients.py) перед этим скриптом.

Использование:
    SOURCE_DATABASE_URL=postgresql://admin:...@host:5440/bd \
    DATABASE_URL=postgresql://pravburo:pravburo@shared_postgres:5432/pravburo \
    DB_SCHEMA=client_search \
    python scripts/etl_import_payments.py
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
        src_cur.execute(
            """select id, client_id, total_amount, discount, first_payment, first_payment_date,
                      number_of_payments, preferred_payment_day, deposit, publication,
                      coalesce(extra_court_costs, false) as extra_court_costs, created_at
               from payments_contract"""
        )
        contracts = src_cur.fetchall()
        psycopg2.extras.execute_values(
            dest_cur,
            """insert into contracts (id, client_id, total_amount, discount, first_payment,
                                       first_payment_date, number_of_payments, preferred_payment_day,
                                       deposit, publication, extra_court_costs, created_at)
               values %s on conflict (id) do nothing""",
            [
                (
                    c["id"], c["client_id"], c["total_amount"], c["discount"], c["first_payment"],
                    c["first_payment_date"], c["number_of_payments"], c["preferred_payment_day"],
                    c["deposit"], c["publication"], c["extra_court_costs"], c["created_at"],
                )
                for c in contracts
            ],
        )
        dest_conn.commit()
        print(f"contracts: {len(contracts)}")

        src_cur.execute("select id, contract_id, calculated, created_at from payments_installmentplan")
        plans = src_cur.fetchall()
        psycopg2.extras.execute_values(
            dest_cur,
            """insert into installment_plans (id, contract_id, calculated, created_at)
               values %s on conflict (id) do nothing""",
            [(p["id"], p["contract_id"], p["calculated"], p["created_at"]) for p in plans],
        )
        dest_conn.commit()
        print(f"installment_plans: {len(plans)}")

        src_cur.execute(
            """select id, plan_id, number, due_date, amount_due, amount_paid, status
               from payments_installmentpayment"""
        )
        installments = src_cur.fetchall()
        psycopg2.extras.execute_values(
            dest_cur,
            """insert into installment_payments (id, plan_id, number, due_date, amount_due, amount_paid, status)
               values %s on conflict (id) do nothing""",
            [
                (i["id"], i["plan_id"], i["number"], i["due_date"], i["amount_due"], i["amount_paid"], i["status"])
                for i in installments
            ],
        )
        dest_conn.commit()
        print(f"installment_payments: {len(installments)}")

        src_cur.execute("select id, plan_id, payment_date, amount, created_at from payments_actualpayment")
        actuals = src_cur.fetchall()
        psycopg2.extras.execute_values(
            dest_cur,
            """insert into actual_payments (id, plan_id, payment_date, amount, created_at)
               values %s on conflict (id) do nothing""",
            [(a["id"], a["plan_id"], a["payment_date"], a["amount"], a["created_at"]) for a in actuals],
        )
        dest_conn.commit()
        print(f"actual_payments: {len(actuals)}")

        src_cur.execute(
            """select id, client_id, payment_type, amount, is_paid, comment, created_at
               from payments_otherpayment"""
        )
        others = src_cur.fetchall()
        psycopg2.extras.execute_values(
            dest_cur,
            """insert into other_payments (id, client_id, payment_type, amount, is_paid, comment, created_at)
               values %s on conflict (id) do nothing""",
            [
                (o["id"], o["client_id"], o["payment_type"], o["amount"], o["is_paid"], o["comment"], o["created_at"])
                for o in others
            ],
        )
        dest_conn.commit()
        print(f"other_payments: {len(others)}")

    for table in ["contracts", "installment_plans", "installment_payments", "actual_payments", "other_payments"]:
        _reset_sequence(dest_conn, table)

    src_conn.close()
    dest_conn.close()


if __name__ == "__main__":
    main()
