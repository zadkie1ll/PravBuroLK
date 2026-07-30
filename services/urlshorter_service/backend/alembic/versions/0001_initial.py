"""initial: url_shorteners + clicks

Revision ID: 0001
Revises:
Create Date: 2026-07-30

"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "url_shorteners",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source", sa.String(100), nullable=False, unique=True),
        sa.Column("destination", sa.String(2000), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_url_shorteners_source", "url_shorteners", ["source"], unique=True)

    op.create_table(
        "clicks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("url_id", sa.Integer(), sa.ForeignKey("url_shorteners.id", ondelete="CASCADE"), nullable=False),
        sa.Column("social", sa.String(50), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("clicked_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_clicks_url_id", "clicks", ["url_id"])


def downgrade() -> None:
    op.drop_table("clicks")
    op.drop_table("url_shorteners")
