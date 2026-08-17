import enum
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class CallEntityType(str, enum.Enum):
    DEAL = "deal"
    LEAD = "lead"


class CallSessionStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class CallQueueItemStatus(str, enum.Enum):
    NEW = "new"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    POSTPONED = "postponed"
    SKIPPED = "skipped"
    FAILED = "failed"


class CallResult(str, enum.Enum):
    NO_ANSWER = "no_answer"
    BUSY = "busy"
    UNAVAILABLE = "unavailable"
    SUCCESS = "success"
    POSTPONED = "postponed"
    SKIPPED = "skipped"


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
    refresh_token_hash: Mapped[str] = mapped_column(String(64), default="")
    refresh_token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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


class CallSession(Base):
    """Соответствует call_queue/models.py:CallSession в монолите — история сессий обзвона.
    Не используется текущей логикой сервиса (та живёт в UserQueueState), существует только
    для переноса истории из монолита при ETL-миграции данных."""

    __tablename__ = "call_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    entity_type: Mapped[str] = mapped_column(String(16), default=CallEntityType.DEAL.value)
    date_from: Mapped[date] = mapped_column(Date())
    date_to: Mapped[date] = mapped_column(Date())
    status: Mapped[str] = mapped_column(String(16), default=CallSessionStatus.DRAFT.value)
    filters_json: Mapped[dict] = mapped_column(JSON, default=dict)
    total_items: Mapped[int] = mapped_column(Integer, default=0)
    processed_items: Mapped[int] = mapped_column(Integer, default=0)
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CallQueueItem(Base):
    """Соответствует call_queue/models.py:CallQueueItem — элемент истории сессии обзвона."""

    __tablename__ = "call_queue_items"
    __table_args__ = (
        UniqueConstraint("session_id", "entity_type", "bitrix_entity_id", name="uq_call_queue_items_session_entity"),
        Index("ix_call_queue_items_session_status", "session_id", "status"),
        Index("ix_call_queue_items_session_assigned", "session_id", "assigned_to_id"),
        Index("ix_call_queue_items_status_locked", "status", "locked_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("call_sessions.id"))
    entity_type: Mapped[str] = mapped_column(String(16), default=CallEntityType.DEAL.value)
    bitrix_entity_id: Mapped[int] = mapped_column(Integer)
    bitrix_contact_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    client_name: Mapped[str] = mapped_column(String(255), default="")
    phone: Mapped[str] = mapped_column(String(64), default="")
    lead_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_id: Mapped[str] = mapped_column(String(64), default="")
    source_name: Mapped[str] = mapped_column(String(255), default="")
    stage_id: Mapped[str] = mapped_column(String(64), default="")
    stage_name: Mapped[str] = mapped_column(String(255), default="")
    responsible_id: Mapped[str] = mapped_column(String(64), default="")
    responsible_name: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(16), default=CallQueueItemStatus.NEW.value)
    assigned_to_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempts_count: Mapped[int] = mapped_column(Integer, default=0)
    last_call_result: Mapped[str] = mapped_column(String(32), default="")
    last_call_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_provider_call_id: Mapped[str] = mapped_column(String(128), default="")
    bitrix_url: Mapped[str] = mapped_column(String(512), default="")
    needs_manual_processing: Mapped[bool] = mapped_column(Boolean, default=False)
    repeat_unanswered: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CallAttempt(Base):
    """Соответствует call_queue/models.py:CallAttempt — попытка дозвона по элементу очереди."""

    __tablename__ = "call_attempts"
    __table_args__ = (
        Index("ix_call_attempts_queue_item_created", "queue_item_id", "created_at"),
        Index("ix_call_attempts_manager_created", "manager_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    queue_item_id: Mapped[int] = mapped_column(ForeignKey("call_queue_items.id"))
    manager_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    result: Mapped[str] = mapped_column(String(32))
    comment: Mapped[str] = mapped_column(Text, default="")
    provider_call_id: Mapped[str] = mapped_column(String(128), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
