"""users: add refresh_token_hash, refresh_token_expires_at

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-17

"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("refresh_token_hash", sa.String(64), nullable=False, server_default=""))
    op.add_column("users", sa.Column("refresh_token_expires_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "refresh_token_expires_at")
    op.drop_column("users", "refresh_token_hash")
