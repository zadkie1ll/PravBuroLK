"""megafon telephony: bitrix_sync_logs + user megafon cache fields

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-20

"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("sales_manager_megafon_user", sa.String(128), nullable=False, server_default=""))
    op.add_column("users", sa.Column("sales_manager_megafon_group", sa.String(128), nullable=False, server_default=""))
    op.add_column("users", sa.Column("sales_manager_megafon_clid", sa.String(64), nullable=False, server_default=""))

    op.add_column("user_queue_state", sa.Column("active_call_id", sa.String(128), nullable=False, server_default=""))
    op.add_column(
        "user_queue_state", sa.Column("last_completed_call_id", sa.String(128), nullable=False, server_default="")
    )

    op.create_table(
        "bitrix_sync_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("entity_id", sa.String(128), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("request_payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("response_payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("error_text", sa.String(1024), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_bitrix_sync_logs_entity", "bitrix_sync_logs", ["entity_type", "entity_id"])
    op.create_index("ix_bitrix_sync_logs_action_created", "bitrix_sync_logs", ["action", "created_at"])
    op.create_index("ix_bitrix_sync_logs_success_created", "bitrix_sync_logs", ["success", "created_at"])


def downgrade() -> None:
    op.drop_table("bitrix_sync_logs")
    op.drop_column("user_queue_state", "last_completed_call_id")
    op.drop_column("user_queue_state", "active_call_id")
    op.drop_column("users", "sales_manager_megafon_clid")
    op.drop_column("users", "sales_manager_megafon_group")
    op.drop_column("users", "sales_manager_megafon_user")
