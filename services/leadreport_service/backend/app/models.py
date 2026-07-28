from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class User(Base):
    """Свой пользователь сервиса (JWT-логин). Создаётся автоматически при синхронизации
    менеджеров из Bitrix (см. services/managers_sync.py) — открытой регистрации нет,
    как и в оригинальном leadreport-приложении монолита."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(150), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), default="")
    hashed_password: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_staff: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SalesManager(Base):
    __tablename__ = "sales_managers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bitrix_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))

    email: Mapped[str] = mapped_column(String(255), default="")
    phone: Mapped[str] = mapped_column(String(64), default="")
    megafon_user: Mapped[str] = mapped_column(String(128), default="")
    megafon_group: Mapped[str] = mapped_column(String(128), default="")
    megafon_clid: Mapped[str] = mapped_column(String(64), default="")

    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), unique=True, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class LeadSource(Base):
    __tablename__ = "lead_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    bitrix_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LeadEntry(Base):
    __tablename__ = "lead_entries"
    __table_args__ = (
        Index("ix_lead_entries_manager_occurred", "manager_id", "occurred_at"),
        Index("ix_lead_entries_occurred", "occurred_at"),
        Index("ix_lead_entries_source", "source_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    manager_id: Mapped[int] = mapped_column(ForeignKey("sales_managers.id"))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    source_id: Mapped[int] = mapped_column(ForeignKey("lead_sources.id"))
    comment: Mapped[str] = mapped_column(Text, default="")
    bitrix_lead_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class IssuedCredentialLog(Base):
    """Лог выдачи логина/пароля. Пароль хранится в открытом виде — доступ только staff.
    Соответствует leadreport/models.py:IssuedCredentialLog в монолите."""

    __tablename__ = "issued_credential_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    manager_id: Mapped[int] = mapped_column(ForeignKey("sales_managers.id"))
    username: Mapped[str] = mapped_column(String(150))
    password: Mapped[str] = mapped_column(String(128))
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
