"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-07-28

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "clients",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("surname", sa.String(100), nullable=False),
        sa.Column("middlename", sa.String(100), nullable=True),
        sa.Column("referral_code", postgresql.UUID(as_uuid=True), nullable=False),
    )

    op.create_table(
        "employees",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("referral_code", postgresql.UUID(as_uuid=True), nullable=False),
    )

    op.create_table(
        "referral_clicks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_type", sa.String(20), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
    )
    op.create_index("ix_referral_clicks_owner", "referral_clicks", ["owner_type", "owner_id"])

    op.create_table(
        "applications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("referral_owner_type", sa.String(20), nullable=True),
        sa.Column("referral_owner_id", sa.Integer(), nullable=True),
    )
    op.create_index("ix_applications_owner", "applications", ["referral_owner_type", "referral_owner_id"])


def downgrade() -> None:
    op.drop_table("applications")
    op.drop_table("referral_clicks")
    op.drop_table("employees")
    op.drop_table("clients")
