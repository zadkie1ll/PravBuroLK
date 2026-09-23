"""bot block: как перестать работать на банки

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-23

"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

# key совпадает с DEEPLINK_BLOCKS в bot_pravburo/tg_bot/app/handlers.py
# (маппится там на блок сценария topic_stop_work_for_banks).
KEY = "banki"
TITLE = "Гайд «Как перестать работать на банки» (PDF)"


def upgrade() -> None:
    bot_blocks = sa.table("bot_blocks", sa.column("key", sa.String), sa.column("title", sa.String))
    op.bulk_insert(bot_blocks, [{"key": KEY, "title": TITLE}])


def downgrade() -> None:
    op.execute(f"DELETE FROM bot_blocks WHERE key = '{KEY}'")
