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
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(150), nullable=False, unique=True),
        sa.Column("email", sa.String(255), nullable=False, server_default=""),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_staff", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_users_username", "users", ["username"])

    op.create_table(
        "sales_managers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("bitrix_user_id", sa.BigInteger(), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False, server_default=""),
        sa.Column("phone", sa.String(64), nullable=False, server_default=""),
        sa.Column("megafon_user", sa.String(128), nullable=False, server_default=""),
        sa.Column("megafon_group", sa.String(128), nullable=False, server_default=""),
        sa.Column("megafon_clid", sa.String(64), nullable=False, server_default=""),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True, unique=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_sales_managers_bitrix_user_id", "sales_managers", ["bitrix_user_id"])

    op.create_table(
        "lead_sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("bitrix_id", sa.BigInteger(), nullable=True, unique=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "lead_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("manager_id", sa.Integer(), sa.ForeignKey("sales_managers.id"), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("lead_sources.id"), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False, server_default=""),
        sa.Column("bitrix_lead_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_lead_entries_manager_occurred", "lead_entries", ["manager_id", "occurred_at"])
    op.create_index("ix_lead_entries_occurred", "lead_entries", ["occurred_at"])
    op.create_index("ix_lead_entries_source", "lead_entries", ["source_id"])
    op.create_index("ix_lead_entries_bitrix_lead_id", "lead_entries", ["bitrix_lead_id"])

    op.create_table(
        "issued_credential_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("manager_id", sa.Integer(), sa.ForeignKey("sales_managers.id"), nullable=False),
        sa.Column("username", sa.String(150), nullable=False),
        sa.Column("password", sa.String(128), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("issued_credential_logs")
    op.drop_table("lead_entries")
    op.drop_table("lead_sources")
    op.drop_table("sales_managers")
    op.drop_table("users")
