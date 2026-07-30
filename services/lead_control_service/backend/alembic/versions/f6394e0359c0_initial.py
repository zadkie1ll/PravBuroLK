"""initial

Revision ID: f6394e0359c0
Revises:
Create Date: 2026-07-30 07:41:21.578730

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'f6394e0359c0'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'lead_monitors',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('bitrix_deal_id', sa.BigInteger(), nullable=False),
        sa.Column('initial_bitrix_task_id', sa.BigInteger(), nullable=True),
        sa.Column('bitrix_task_id', sa.BigInteger(), nullable=True),
        sa.Column('moderator_bitrix_user_id', sa.BigInteger(), nullable=True),
        sa.Column('responsible_bitrix_user_id', sa.BigInteger(), nullable=True),
        sa.Column('task_description', sa.Text(), nullable=False),
        sa.Column('initial_task_created', sa.Boolean(), nullable=False),
        sa.Column('attempts_total', sa.SmallInteger(), nullable=False),
        sa.Column('attempts_today', sa.SmallInteger(), nullable=False),
        sa.Column('attempts_last_reset_date', sa.Date(), nullable=True),
        sa.Column('entered_logic_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('current_stage_id', sa.String(length=255), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('status_comment', sa.Text(), nullable=False),
        sa.Column('last_task_closed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_moderator_task_created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_moderator_task_id', sa.BigInteger(), nullable=True),
        sa.Column('last_checked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('raw_deal_data', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('bitrix_deal_id'),
    )
    op.create_index('ix_lead_monitors_active_status', 'lead_monitors', ['is_active', 'status'])
    op.create_index('ix_lead_monitors_bitrix_deal_id', 'lead_monitors', ['bitrix_deal_id'])
    op.create_index('ix_lead_monitors_responsible', 'lead_monitors', ['responsible_bitrix_user_id'])
    op.create_index('ix_lead_monitors_stage', 'lead_monitors', ['current_stage_id'])


def downgrade() -> None:
    op.drop_index('ix_lead_monitors_stage', table_name='lead_monitors')
    op.drop_index('ix_lead_monitors_responsible', table_name='lead_monitors')
    op.drop_index('ix_lead_monitors_bitrix_deal_id', table_name='lead_monitors')
    op.drop_index('ix_lead_monitors_active_status', table_name='lead_monitors')
    op.drop_table('lead_monitors')
