"""dashboard visit stats

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-28

"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "visit_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("visited_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_visit_events_visited_at", "visit_events", ["visited_at"])


def downgrade() -> None:
    op.drop_table("visit_events")
