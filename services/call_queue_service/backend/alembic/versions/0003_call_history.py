"""call history: call_sessions, call_queue_items, call_attempts

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-27

"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "call_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("entity_type", sa.String(16), nullable=False, server_default="deal"),
        sa.Column("date_from", sa.Date(), nullable=False),
        sa.Column("date_to", sa.Date(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("filters_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("total_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("processed_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("success_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "call_queue_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("call_sessions.id"), nullable=False),
        sa.Column("entity_type", sa.String(16), nullable=False, server_default="deal"),
        sa.Column("bitrix_entity_id", sa.Integer(), nullable=False),
        sa.Column("bitrix_contact_id", sa.Integer(), nullable=True),
        sa.Column("client_name", sa.String(255), nullable=False, server_default=""),
        sa.Column("phone", sa.String(64), nullable=False, server_default=""),
        sa.Column("lead_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_id", sa.String(64), nullable=False, server_default=""),
        sa.Column("source_name", sa.String(255), nullable=False, server_default=""),
        sa.Column("stage_id", sa.String(64), nullable=False, server_default=""),
        sa.Column("stage_name", sa.String(255), nullable=False, server_default=""),
        sa.Column("responsible_id", sa.String(64), nullable=False, server_default=""),
        sa.Column("responsible_name", sa.String(255), nullable=False, server_default=""),
        sa.Column("status", sa.String(16), nullable=False, server_default="new"),
        sa.Column("assigned_to_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_call_result", sa.String(32), nullable=False, server_default=""),
        sa.Column("last_call_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_provider_call_id", sa.String(128), nullable=False, server_default=""),
        sa.Column("bitrix_url", sa.String(512), nullable=False, server_default=""),
        sa.Column("needs_manual_processing", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("repeat_unanswered", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "session_id", "entity_type", "bitrix_entity_id", name="uq_call_queue_items_session_entity"
        ),
    )
    op.create_index("ix_call_queue_items_session_status", "call_queue_items", ["session_id", "status"])
    op.create_index("ix_call_queue_items_session_assigned", "call_queue_items", ["session_id", "assigned_to_id"])
    op.create_index("ix_call_queue_items_status_locked", "call_queue_items", ["status", "locked_at"])

    op.create_table(
        "call_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("queue_item_id", sa.Integer(), sa.ForeignKey("call_queue_items.id"), nullable=False),
        sa.Column("manager_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("result", sa.String(32), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False, server_default=""),
        sa.Column("provider_call_id", sa.String(128), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_call_attempts_queue_item_created", "call_attempts", ["queue_item_id", "created_at"])
    op.create_index("ix_call_attempts_manager_created", "call_attempts", ["manager_id", "created_at"])


def downgrade() -> None:
    op.drop_table("call_attempts")
    op.drop_table("call_queue_items")
    op.drop_table("call_sessions")
