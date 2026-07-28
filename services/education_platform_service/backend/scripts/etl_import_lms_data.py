"""One-shot ETL: копирует данные LMS из монолита (education_platform_* в схеме public,
Django ORM) в схему education_platform_service.

Почти все таблицы совпадают 1-в-1 (courses/modules/module_materials/module_tests/
test_questions/question_options/learning_progress/test_attempts/answer_errors) — переносятся
как есть, с сохранением id. TraineeProfile в новом сервисе не отдельная таблица, а поля прямо
в users (birthday/started_at/stats/departments) — при переносе трейни сливаются в User по
username. Django-пароли не переносятся (PBKDF2 в bcrypt-схему этого сервиса не конвертируется),
созданным пользователям ставится нерабочий плейсхолдер-хэш.

Известный пробел: Django ProgressEvent (education_platform/models.py:270) не имеет аналога
в этом сервисе — на момент написания в проде там 0 строк, так что для текущего переноса
это не потеря данных, но если до реального cutover в монолите накопится история эту таблицу
предстоит добавить в сервис так же, как это было сделано для call_queue_service (0003).

Идемпотентно: ON CONFLICT DO NOTHING по PK, пользователи ищутся/создаются по username.

Использование:
    SOURCE_DATABASE_URL=postgresql://admin:...@host:5440/bd \
    DATABASE_URL=postgresql://pravburo:pravburo@shared_postgres:5432/pravburo \
    DB_SCHEMA=education_platform \
    python scripts/etl_import_lms_data.py
"""
from __future__ import annotations

import os
import secrets

import psycopg2
import psycopg2.extras


def _connect(url: str, schema: str | None = None):
    conn = psycopg2.connect(url)
    if schema:
        with conn.cursor() as cur:
            cur.execute(f"SET search_path TO {schema}")
    return conn


def _placeholder_password_hash() -> str:
    return "!imported-" + secrets.token_hex(16)


def _copy_table(src_cur, dest_cur, select_sql: str, insert_sql: str, row_to_params) -> int:
    src_cur.execute(select_sql)
    rows = src_cur.fetchall()
    for row in rows:
        dest_cur.execute(insert_sql, row_to_params(row))
    return len(rows)


def _reset_sequence(dest_cur, table: str, id_column: str = "id") -> None:
    dest_cur.execute(
        f"select setval(pg_get_serial_sequence(%s, %s), coalesce((select max({id_column}) from {table}), 1), "
        f"(select max({id_column}) from {table}) is not null)",
        (table, id_column),
    )


def _load_trainee_user_map(src_cur, dest_conn) -> dict[int, int]:
    """trainee_id (education_platform_traineeprofile.id) -> new users.id, matched by username."""

    src_cur.execute(
        """
        select tp.id as trainee_id, u.username, u.first_name, u.last_name, u.is_staff, u.is_active,
               tp.birthday, tp.started_at, tp.stats
        from education_platform_traineeprofile tp
        join auth_user u on u.id = tp.user_id
        """
    )
    trainees = src_cur.fetchall()

    mapping: dict[int, int] = {}
    with dest_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as dest_cur:
        for row in trainees:
            dest_cur.execute("select id from users where username = %s", (row["username"],))
            existing = dest_cur.fetchone()
            if existing:
                mapping[row["trainee_id"]] = existing["id"]
                continue

            dest_cur.execute(
                """
                insert into users
                    (username, hashed_password, first_name, last_name, is_active, is_staff,
                     birthday, started_at, stats)
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                returning id
                """,
                (
                    row["username"],
                    _placeholder_password_hash(),
                    row["first_name"],
                    row["last_name"],
                    row["is_active"],
                    row["is_staff"],
                    row["birthday"],
                    row["started_at"],
                    psycopg2.extras.Json(row["stats"]),
                ),
            )
            mapping[row["trainee_id"]] = dest_cur.fetchone()["id"]

    dest_conn.commit()
    return mapping


def main() -> None:
    source_url = os.environ["SOURCE_DATABASE_URL"]
    dest_url = os.environ.get("DATABASE_URL", "postgresql://pravburo:pravburo@shared_postgres:5432/pravburo")
    dest_schema = os.environ.get("DB_SCHEMA", "education_platform")

    src_conn = _connect(source_url)
    dest_conn = _connect(dest_url, schema=dest_schema)

    with src_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as src_cur:
        trainee_user_map = _load_trainee_user_map(src_cur, dest_conn)
        print(f"User map: {len(trainee_user_map)} trainee(s) resolved/created")

        with dest_conn.cursor() as dest_cur:
            n = _copy_table(
                src_cur, dest_cur,
                "select id, code, name, is_active from education_platform_department",
                """insert into departments (id, code, name, is_active) values (%s, %s, %s, %s)
                   on conflict (id) do nothing""",
                lambda r: (r["id"], r["code"], r["name"], r["is_active"]),
            )
            print(f"departments: {n} row(s)")

            n = _copy_table(
                src_cur, dest_cur,
                """select id, name, description, image_url, photo_url, is_active, created_at, updated_at
                   from education_platform_course""",
                """insert into courses
                       (id, name, description, image_url, photo_url, is_active, created_at, updated_at)
                   values (%s, %s, %s, %s, %s, %s, %s, %s)
                   on conflict (id) do nothing""",
                lambda r: (
                    r["id"], r["name"], r["description"], r["image_url"], r["photo_url"],
                    r["is_active"], r["created_at"], r["updated_at"],
                ),
            )
            print(f"courses: {n} row(s)")

            n = _copy_table(
                src_cur, dest_cur,
                "select course_id, department_id from education_platform_course_departments",
                """insert into course_departments (course_id, department_id) values (%s, %s)
                   on conflict do nothing""",
                lambda r: (r["course_id"], r["department_id"]),
            )
            print(f"course_departments: {n} row(s)")

            n = _copy_table(
                src_cur, dest_cur,
                """select id, course_id, name, description, video_url, private_video, "order",
                          is_active, created_at, updated_at
                   from education_platform_module""",
                """insert into modules
                       (id, course_id, name, description, video_url, private_video, "order",
                        is_active, created_at, updated_at)
                   values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   on conflict (id) do nothing""",
                lambda r: (
                    r["id"], r["course_id"], r["name"], r["description"], r["video_url"],
                    r["private_video"], r["order"], r["is_active"], r["created_at"], r["updated_at"],
                ),
            )
            print(f"modules: {n} row(s)")

            n = _copy_table(
                src_cur, dest_cur,
                """select id, module_id, title, material_type, file, "order", is_active,
                          created_at, updated_at
                   from education_platform_modulematerial""",
                """insert into module_materials
                       (id, module_id, title, material_type, file, "order", is_active,
                        created_at, updated_at)
                   values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                   on conflict (id) do nothing""",
                lambda r: (
                    r["id"], r["module_id"], r["title"], r["material_type"], r["file"],
                    r["order"], r["is_active"], r["created_at"], r["updated_at"],
                ),
            )
            print(f"module_materials: {n} row(s)")

            n = _copy_table(
                src_cur, dest_cur,
                """select id, module_id, name, description, max_score, passing_score, max_attempts,
                          is_active, created_at, updated_at
                   from education_platform_moduletest""",
                """insert into module_tests
                       (id, module_id, name, description, max_score, passing_score, max_attempts,
                        is_active, created_at, updated_at)
                   values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   on conflict (id) do nothing""",
                lambda r: (
                    r["id"], r["module_id"], r["name"], r["description"], r["max_score"],
                    r["passing_score"], r["max_attempts"], r["is_active"], r["created_at"], r["updated_at"],
                ),
            )
            print(f"module_tests: {n} row(s)")

            n = _copy_table(
                src_cur, dest_cur,
                'select id, test_id, text, question_type, score, "order" from education_platform_testquestion',
                """insert into test_questions (id, test_id, text, question_type, score, "order")
                   values (%s, %s, %s, %s, %s, %s)
                   on conflict (id) do nothing""",
                lambda r: (r["id"], r["test_id"], r["text"], r["question_type"], r["score"], r["order"]),
            )
            print(f"test_questions: {n} row(s)")

            n = _copy_table(
                src_cur, dest_cur,
                'select id, question_id, text, is_correct, "order" from education_platform_questionoption',
                """insert into question_options (id, question_id, text, is_correct, "order")
                   values (%s, %s, %s, %s, %s)
                   on conflict (id) do nothing""",
                lambda r: (r["id"], r["question_id"], r["text"], r["is_correct"], r["order"]),
            )
            print(f"question_options: {n} row(s)")

            n = _copy_table(
                src_cur, dest_cur,
                "select traineeprofile_id, department_id from education_platform_traineeprofile_departments",
                """insert into user_departments (user_id, department_id) values (%s, %s)
                   on conflict do nothing""",
                lambda r: (trainee_user_map[r["traineeprofile_id"]], r["department_id"]),
            )
            print(f"user_departments: {n} row(s)")

            n = _copy_table(
                src_cur, dest_cur,
                """select id, trainee_id, block_id, status, started_at, completed_at, current_step,
                          last_activity_at, meta, created_at, updated_at
                   from education_platform_learningprogress""",
                """insert into learning_progress
                       (id, user_id, block_id, status, started_at, completed_at, current_step,
                        last_activity_at, meta, created_at, updated_at)
                   values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   on conflict (id) do nothing""",
                lambda r: (
                    r["id"], trainee_user_map[r["trainee_id"]], r["block_id"], r["status"],
                    r["started_at"], r["completed_at"], r["current_step"], r["last_activity_at"],
                    psycopg2.extras.Json(r["meta"]), r["created_at"], r["updated_at"],
                ),
            )
            print(f"learning_progress: {n} row(s)")

            n = _copy_table(
                src_cur, dest_cur,
                """select id, trainee_id, test_id, status, attempt_number, score, max_score, passed,
                          started_at, finished_at, meta, created_at, updated_at
                   from education_platform_testattempt""",
                """insert into test_attempts
                       (id, user_id, test_id, status, attempt_number, score, max_score, passed,
                        started_at, finished_at, meta, created_at, updated_at)
                   values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   on conflict (id) do nothing""",
                lambda r: (
                    r["id"], trainee_user_map[r["trainee_id"]], r["test_id"], r["status"],
                    r["attempt_number"], r["score"], r["max_score"], r["passed"],
                    r["started_at"], r["finished_at"], psycopg2.extras.Json(r["meta"]),
                    r["created_at"], r["updated_at"],
                ),
            )
            print(f"test_attempts: {n} row(s)")

            n = _copy_table(
                src_cur, dest_cur,
                """select id, attempt_id, question_id, answer_type, error_type, user_answer,
                          correct_answer, metadata, created_at
                   from education_platform_answererror""",
                """insert into answer_errors
                       (id, attempt_id, question_id, answer_type, error_type, user_answer,
                        correct_answer, metadata, created_at)
                   values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                   on conflict (id) do nothing""",
                lambda r: (
                    r["id"], r["attempt_id"], r["question_id"], r["answer_type"], r["error_type"],
                    psycopg2.extras.Json(r["user_answer"]), psycopg2.extras.Json(r["correct_answer"]),
                    psycopg2.extras.Json(r["metadata"]), r["created_at"],
                ),
            )
            print(f"answer_errors: {n} row(s)")

            for table in (
                "departments", "courses", "users", "modules", "module_materials", "module_tests",
                "test_questions", "question_options", "learning_progress", "test_attempts", "answer_errors",
            ):
                _reset_sequence(dest_cur, table)

        dest_conn.commit()
    print("Done.")


if __name__ == "__main__":
    main()
