"""client withdrawals: списания клиента (folded in from client_withdrawals monolith app)

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-30

"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "withdrawal_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id"), nullable=False),
        sa.Column("withdrawal_date", sa.Date(), nullable=True),
        sa.Column("transfer_date", sa.Date(), nullable=True),
        sa.Column("withdrawal_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("transferred_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("tail_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("comment", sa.String(255), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_withdrawal_records_client_id", "withdrawal_records", ["client_id"])


def downgrade() -> None:
    op.drop_table("withdrawal_records")
