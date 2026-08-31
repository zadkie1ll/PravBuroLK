from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class UrlShortener(Base):
    """Порт urlshorter/models.py:UrlShortener."""

    __tablename__ = "url_shorteners"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    destination: Mapped[str] = mapped_column(String(2000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    clicks = relationship("Click", back_populates="url", cascade="all, delete-orphan")


class Click(Base):
    """Порт urlshorter/models.py:Click."""

    __tablename__ = "clicks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    url_id: Mapped[int] = mapped_column(ForeignKey("url_shorteners.id", ondelete="CASCADE"), index=True)
    social: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    clicked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    url = relationship("UrlShortener", back_populates="clicks")


# --- Новая система разметки (порт urlshorter/models.py второй половины монолита) ---
# Отдельные таблицы, легаси-модели выше не трогают вообще.


class UtmSource(Base):
    __tablename__ = "utm_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(100), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class UtmMedium(Base):
    __tablename__ = "utm_mediums"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class BotBlock(Base):
    __tablename__ = "bot_blocks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(50), unique=True)
    title: Mapped[str] = mapped_column(String(200))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class MarketingLink(Base):
    __tablename__ = "marketing_links"
    __table_args__ = (
        UniqueConstraint(
            "link_type", "destination", "utm_source_id", "utm_medium_id",
            "utm_campaign", "utm_content", "utm_term", "bot_block_id",
            name="uq_marketing_link_combo",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(150), unique=True, index=True)
    link_type: Mapped[str] = mapped_column(String(10))  # site / bot / other
    destination: Mapped[str] = mapped_column(String(2000))

    utm_source_id: Mapped[int] = mapped_column(ForeignKey("utm_sources.id"))
    utm_medium_id: Mapped[int] = mapped_column(ForeignKey("utm_mediums.id"))
    utm_campaign: Mapped[str] = mapped_column(String(100))
    utm_content: Mapped[str] = mapped_column(String(100), default="")
    utm_term: Mapped[str] = mapped_column(String(100), default="")

    bot_block_id: Mapped[int | None] = mapped_column(ForeignKey("bot_blocks.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    utm_source = relationship("UtmSource")
    utm_medium = relationship("UtmMedium")
    bot_block = relationship("BotBlock")
    clicks = relationship("MarketingClick", back_populates="link", cascade="all, delete-orphan")


BOT_PREVIEW_USER_AGENTS = (
    "TelegramBot",
    "vkShare",
    "facebookexternalhit",
    "Twitterbot",
    "WhatsApp",
    "SkypeUriPreview",
)


class MarketingClick(Base):
    __tablename__ = "marketing_clicks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    link_id: Mapped[int] = mapped_column(ForeignKey("marketing_links.id", ondelete="CASCADE"), index=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_bot_preview: Mapped[bool] = mapped_column(Boolean, default=False)
    clicked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    link = relationship("MarketingLink", back_populates="clicks")
