"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-07-28

"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stage_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
    )

    op.create_table(
        "clients",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("surname", sa.String(100), nullable=False),
        sa.Column("middlename", sa.String(100), nullable=True),
        sa.Column("bitrix_id", sa.String(255), nullable=True),
        sa.Column("stage_id", sa.Integer(), sa.ForeignKey("stage_templates.id"), nullable=True),
        sa.Column("is_blocked", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_clients_bitrix_id", "clients", ["bitrix_id"])
    op.create_index("ix_clients_surname_name", "clients", ["surname", "name"])


def downgrade() -> None:
    op.drop_table("clients")
    op.drop_table("stage_templates")
