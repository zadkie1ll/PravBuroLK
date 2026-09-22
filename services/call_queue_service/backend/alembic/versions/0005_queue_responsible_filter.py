"""user_queue_state: add responsible_id filter

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-22

"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_queue_state",
        sa.Column("responsible_id", sa.String(64), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("user_queue_state", "responsible_id")
