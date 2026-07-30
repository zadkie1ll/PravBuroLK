from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
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
