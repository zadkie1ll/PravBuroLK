"""clicks: composite index for retry-dedup lookup

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-19

"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_clicks_dedup_lookup",
        "clicks",
        ["url_id", "ip_address", "clicked_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_clicks_dedup_lookup", table_name="clicks")
