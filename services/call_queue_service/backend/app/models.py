import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class CallEntityType(str, enum.Enum):
    DEAL = "deal"
    LEAD = "lead"


class User(Base):
    """Свой пользователь сервиса (JWT-логин), не связан с монолитом напрямую.
    sales_manager_* — кэш данных, полученных по email из leadreport-эндпоинта монолита."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sales_manager_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sales_manager_name: Mapped[str] = mapped_column(String(255), default="")
    sales_manager_megafon_user: Mapped[str] = mapped_column(String(128), default="")
    sales_manager_megafon_group: Mapped[str] = mapped_column(String(128), default="")
    sales_manager_megafon_clid: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserQueueState(Base):
    """Персистентный аналог Django-сессии (request.session) из call_queue/views.py:
    get_prod_queue/save_prod_queue/get_prod_queue_index — одна текущая очередь на менеджера,
    без отдельных 'сессий обзвона' как самостоятельных объектов (как и в оригинале)."""

    __tablename__ = "user_queue_state"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    queue_json: Mapped[list] = mapped_column(JSON, default=list)
    queue_index: Mapped[int] = mapped_column(Integer, default=0)
    entity_type: Mapped[str] = mapped_column(String(16), default=CallEntityType.DEAL.value)
    date_from: Mapped[str] = mapped_column(String(16), default="")
    date_to: Mapped[str] = mapped_column(String(16), default="")
    stage_id: Mapped[str] = mapped_column(String(64), default="")
    auto_dial: Mapped[bool] = mapped_column(Boolean, default=True)
    custom_entity_type: Mapped[str] = mapped_column(String(16), default=CallEntityType.DEAL.value)
    custom_category_id: Mapped[str] = mapped_column(String(64), default="")
    active_call_id: Mapped[str] = mapped_column(String(128), default="")
    last_completed_call_id: Mapped[str] = mapped_column(String(128), default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class BitrixSyncLog(Base):
    """Лог вызовов в Bitrix и вебхуков МегаФона — соответствует call_queue/models.py:BitrixSyncLog
    в оригинале (используется build_megafon_call_snapshot для чтения таймлайна звонка)."""

    __tablename__ = "bitrix_sync_logs"
    __table_args__ = (
        Index("ix_bitrix_sync_logs_entity", "entity_type", "entity_id"),
        Index("ix_bitrix_sync_logs_action_created", "action", "created_at"),
        Index("ix_bitrix_sync_logs_success_created", "success", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[str] = mapped_column(String(128))
    action: Mapped[str] = mapped_column(String(64))
    request_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    response_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    success: Mapped[bool] = mapped_column(Boolean, default=False)
    error_text: Mapped[str] = mapped_column(String(1024), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
