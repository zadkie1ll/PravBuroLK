"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-07-20

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
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sales_manager_id", sa.Integer(), nullable=True),
        sa.Column("sales_manager_name", sa.String(255), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "user_queue_state",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("queue_json", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("queue_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("entity_type", sa.String(16), nullable=False, server_default="deal"),
        sa.Column("date_from", sa.String(16), nullable=False, server_default=""),
        sa.Column("date_to", sa.String(16), nullable=False, server_default=""),
        sa.Column("stage_id", sa.String(64), nullable=False, server_default=""),
        sa.Column("auto_dial", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("custom_entity_type", sa.String(16), nullable=False, server_default="deal"),
        sa.Column("custom_category_id", sa.String(64), nullable=False, server_default=""),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("user_queue_state")
    op.drop_table("users")
