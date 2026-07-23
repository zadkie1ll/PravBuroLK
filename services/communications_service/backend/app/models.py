import enum
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class CallStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"
    IGNORED = "ignored"


class CallWebhookEvent(Base):
    """Порт communications.models.CallWebhookEvent из монолита."""

    __tablename__ = "call_webhook_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    event_name: Mapped[str] = mapped_column(String(128), default="")
    call_id: Mapped[str] = mapped_column(String(128), default="", index=True)
    lead_id: Mapped[str] = mapped_column(String(128), default="")
    deal_id: Mapped[str] = mapped_column(String(128), default="")
    contact_id: Mapped[str] = mapped_column(String(128), default="")
    record_file_id: Mapped[str] = mapped_column(String(128), default="")
    dedupe_key: Mapped[str] = mapped_column(String(255), default="", index=True)
    status: Mapped[str] = mapped_column(String(16), default=CallStatus.PENDING.value, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    raw_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    audio_file_path: Mapped[str] = mapped_column(String(512), default="")
    transcript: Mapped[list] = mapped_column(JSON, default=list)
    analysis: Mapped[dict] = mapped_column(JSON, default=dict)
    error_message: Mapped[str] = mapped_column(Text, default="")


class CallProcessingLog(Base):
    """Порт communications.models.CallProcessingLog."""

    __tablename__ = "call_processing_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    event_id: Mapped[int] = mapped_column(ForeignKey("call_webhook_events.id"), index=True)
    level: Mapped[str] = mapped_column(String(16), default="info")
    message: Mapped[str] = mapped_column(String(512))
    details: Mapped[dict] = mapped_column(JSON, default=dict)


class ProcessedCallArchive(Base):
    """Порт communications.models.ProcessedCallArchive.

    В монолите жил в отдельной archive-БД (COMMUNICATIONS_SPLIT_DATABASES), чтобы не засорять
    основную БД шумовыми webhook-событиями. В сервисе это больше не нужно — у сервиса и так своя
    выделенная схема, поэтому таблица просто лежит рядом с остальными.
    """

    __tablename__ = "processed_call_archive"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    source_event_id: Mapped[int] = mapped_column(Integer, index=True)
    call_id: Mapped[str] = mapped_column(String(128), default="", index=True)
    lead_id: Mapped[str] = mapped_column(String(128), default="", index=True)
    deal_id: Mapped[str] = mapped_column(String(128), default="", index=True)
    contact_id: Mapped[str] = mapped_column(String(128), default="", index=True)
    record_file_id: Mapped[str] = mapped_column(String(128), default="")
    audio_file_path: Mapped[str] = mapped_column(String(512), default="")
    transcript: Mapped[list] = mapped_column(JSON, default=list)
    analysis: Mapped[dict] = mapped_column(JSON, default=dict)
    source_payload: Mapped[dict] = mapped_column(JSON, default=dict)
