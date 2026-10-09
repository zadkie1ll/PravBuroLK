"""seed default education departments"""

from alembic import op
import sqlalchemy as sa


revision = "6c2f1b7a9e40"
down_revision = "57bf4471895d"
branch_labels = None
depends_on = None


DEPARTMENTS = (
    {"code": "sales", "name": "Продажи", "is_active": True},
    {"code": "marketing", "name": "Маркетинг", "is_active": True},
    {"code": "moderation", "name": "Модерация", "is_active": True},
    {"code": "firstline", "name": "Первая линия", "is_active": True},
    {"code": "support", "name": "Сопровождение", "is_active": True},
    {"code": "law", "name": "Юридический", "is_active": True},
)


def upgrade() -> None:
    departments = sa.table(
        "departments",
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("is_active", sa.Boolean),
    )
    # The unique code makes this safe for databases that already contain
    # some departments after a manual setup or data import.
    connection = op.get_bind()
    for department in DEPARTMENTS:
        connection.execute(
            sa.text(
                """
                INSERT INTO departments (code, name, is_active)
                VALUES (:code, :name, :is_active)
                ON CONFLICT (code) DO UPDATE
                SET name = EXCLUDED.name, is_active = EXCLUDED.is_active
                """
            ),
            department,
        )


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text("DELETE FROM departments WHERE code IN :codes").bindparams(
            sa.bindparam("codes", expanding=True)
        ),
        {"codes": [item["code"] for item in DEPARTMENTS]},
    )
