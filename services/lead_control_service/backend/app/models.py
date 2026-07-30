import enum
from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Index, Integer, JSON, SmallInteger, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class LeadMonitorStatus(str, enum.Enum):
    NEW = "new"
    ACTIVE = "active"
    SUCCESS = "success"
    STOPPED = "stopped"
    SKIPPED = "skipped"
    ERROR = "error"


class LeadMonitor(Base):
    """Порт lead_control.models.LeadMonitor из монолита."""

    __tablename__ = "lead_monitors"
    __table_args__ = (
        Index("ix_lead_monitors_active_status", "is_active", "status"),
        Index("ix_lead_monitors_responsible", "responsible_bitrix_user_id"),
        Index("ix_lead_monitors_stage", "current_stage_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    bitrix_deal_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)

    initial_bitrix_task_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    bitrix_task_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    moderator_bitrix_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    responsible_bitrix_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    task_description: Mapped[str] = mapped_column(Text, default="")

    initial_task_created: Mapped[bool] = mapped_column(Boolean, default=False)

    attempts_total: Mapped[int] = mapped_column(SmallInteger, default=0)
    attempts_today: Mapped[int] = mapped_column(SmallInteger, default=0)
    attempts_last_reset_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    entered_logic_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    current_stage_id: Mapped[str] = mapped_column(String(255), default="")

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(20), default=LeadMonitorStatus.NEW.value)
    status_comment: Mapped[str] = mapped_column(Text, default="")

    last_task_closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_moderator_task_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_moderator_task_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    raw_deal_data: Mapped[dict] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def reset_daily_attempts_if_needed(self, today: date) -> None:
        if self.attempts_last_reset_date != today:
            self.attempts_today = 0
            self.attempts_last_reset_date = today
