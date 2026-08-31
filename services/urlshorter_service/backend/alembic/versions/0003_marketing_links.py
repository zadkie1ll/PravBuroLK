"""marketing links: utm dictionaries + marketing_links/marketing_clicks

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-27

"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

UTM_SOURCES = [
    "youtube-stas", "youtube-pb", "vk-stas", "vk-pb",
    "instagram-stas", "instagram-pb", "telegram-stas", "telegram-pb",
    "tiktok-old", "tiktok-new", "dzen", "max", "taplink", "site",
    "avito", "partner", "email", "bot", "chat", "checklist",
]

UTM_MEDIUMS = ["cpc", "organic"]

BOT_BLOCKS = [
    ("consultation", "Старт бесплатной консультации, бот сразу начинает опрос"),
    ("chat", "Приглашение в закрытый чат поддержки должников"),
    ("pristavi", "Заявление приставу о сохранении прожиточного минимума при взыскании"),
    ("kollektory", "Видео о правах должника при общении с коллекторами"),
    ("mfc", "Видео об условиях бесплатного банкротства через МФЦ"),
    ("prikaz", "Заявление на отмену судебного приказа"),
    ("sid", "Видео про списание долга по сроку исковой давности"),
    ("detskie", "Заявление приставу о снятии ареста со счёта с детскими пособиями"),
    ("otmena", "Заявление на отзыв согласия банку на списание со счетов"),
    ("checklist", "Меню бесплатных чек-листов и гайдов"),
]


def upgrade() -> None:
    op.create_table(
        "utm_sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(100), nullable=False, unique=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )

    op.create_table(
        "utm_mediums",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(50), nullable=False, unique=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )

    op.create_table(
        "bot_blocks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(50), nullable=False, unique=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )

    op.create_table(
        "marketing_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source", sa.String(150), nullable=False, unique=True),
        sa.Column("link_type", sa.String(10), nullable=False),
        sa.Column("destination", sa.String(2000), nullable=False),
        sa.Column("utm_source_id", sa.Integer(), sa.ForeignKey("utm_sources.id"), nullable=False),
        sa.Column("utm_medium_id", sa.Integer(), sa.ForeignKey("utm_mediums.id"), nullable=False),
        sa.Column("utm_campaign", sa.String(100), nullable=False),
        sa.Column("utm_content", sa.String(100), nullable=False, server_default=""),
        sa.Column("utm_term", sa.String(100), nullable=False, server_default=""),
        sa.Column("bot_block_id", sa.Integer(), sa.ForeignKey("bot_blocks.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "link_type", "destination", "utm_source_id", "utm_medium_id",
            "utm_campaign", "utm_content", "utm_term", "bot_block_id",
            name="uq_marketing_link_combo",
        ),
    )
    op.create_index("ix_marketing_links_source", "marketing_links", ["source"], unique=True)

    op.create_table(
        "marketing_clicks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("link_id", sa.Integer(), sa.ForeignKey("marketing_links.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("is_bot_preview", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("clicked_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_marketing_clicks_link_id", "marketing_clicks", ["link_id"])

    utm_sources = sa.table("utm_sources", sa.column("code", sa.String))
    op.bulk_insert(utm_sources, [{"code": code} for code in UTM_SOURCES])

    utm_mediums = sa.table("utm_mediums", sa.column("code", sa.String))
    op.bulk_insert(utm_mediums, [{"code": code} for code in UTM_MEDIUMS])

    bot_blocks = sa.table("bot_blocks", sa.column("key", sa.String), sa.column("title", sa.String))
    op.bulk_insert(bot_blocks, [{"key": key, "title": title} for key, title in BOT_BLOCKS])


def downgrade() -> None:
    op.drop_table("marketing_clicks")
    op.drop_table("marketing_links")
    op.drop_table("bot_blocks")
    op.drop_table("utm_mediums")
    op.drop_table("utm_sources")
