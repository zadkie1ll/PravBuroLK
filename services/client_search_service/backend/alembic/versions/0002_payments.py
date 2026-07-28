"""client detail page: contracts/installment plans/payments

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
        "contracts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id"), nullable=False),
        sa.Column("total_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("discount", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("first_payment", sa.Numeric(10, 2), nullable=False),
        sa.Column("first_payment_date", sa.Date(), nullable=False),
        sa.Column("number_of_payments", sa.Integer(), nullable=False),
        sa.Column("preferred_payment_day", sa.Integer(), nullable=False, server_default="15"),
        sa.Column("deposit", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("publication", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("extra_court_costs", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_contracts_client_id", "contracts", ["client_id"])

    op.create_table(
        "installment_plans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("contract_id", sa.Integer(), sa.ForeignKey("contracts.id"), nullable=False, unique=True),
        sa.Column("calculated", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "installment_payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("plan_id", sa.Integer(), sa.ForeignKey("installment_plans.id"), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("amount_due", sa.Numeric(10, 2), nullable=False),
        sa.Column("amount_paid", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("status", sa.String(10), nullable=False, server_default="pending"),
    )
    op.create_index("ix_installment_payments_plan_id", "installment_payments", ["plan_id"])

    op.create_table(
        "actual_payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("plan_id", sa.Integer(), sa.ForeignKey("installment_plans.id"), nullable=True),
        sa.Column("payment_date", sa.Date(), nullable=True),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_actual_payments_plan_id", "actual_payments", ["plan_id"])

    op.create_table(
        "other_payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id"), nullable=False),
        sa.Column("payment_type", sa.String(20), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("is_paid", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_other_payments_client_id", "other_payments", ["client_id"])


def downgrade() -> None:
    op.drop_table("other_payments")
    op.drop_table("actual_payments")
    op.drop_table("installment_payments")
    op.drop_table("installment_plans")
    op.drop_table("contracts")
