from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, Integer, SmallInteger, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from lsl.core.db import Base


class TaskModel(Base):
    __tablename__ = "tasks"
    __table_args__ = {"schema": "public"}

    task_id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    object_key: Mapped[str] = mapped_column(Text, nullable=False)
    audio_url: Mapped[str] = mapped_column(Text, nullable=False)
    duration_ms: Mapped[int | None] = mapped_column("x_duration_ms", Integer, nullable=True)
    status: Mapped[int] = mapped_column("x_status", SmallInteger, nullable=False, server_default=text("0"))
    language: Mapped[str | None] = mapped_column("x_language", String(16), nullable=True)
    provider: Mapped[str | None] = mapped_column("x_provider", String(32), nullable=True)
    provider_request_id: Mapped[str | None] = mapped_column("x_provider_request_id", String(128), nullable=True)
    provider_resource_id: Mapped[str | None] = mapped_column("x_provider_resource_id", String(128), nullable=True)
    x_tt_logid: Mapped[str | None] = mapped_column(nullable=True)
    provider_status_code: Mapped[str | None] = mapped_column("x_provider_status_code", String(32), nullable=True)
    provider_message: Mapped[str | None] = mapped_column("x_provider_message", Text, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    poll_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    last_polled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_poll_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=text("NOW()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=text("NOW()"),
    )


class AsrResultModel(Base):
    __tablename__ = "asr_results"
    __table_args__ = {"schema": "public"}

    task_id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    provider: Mapped[str | None] = mapped_column("x_provider", String(32), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    full_text: Mapped[str | None] = mapped_column("x_full_text", Text, nullable=True)
    raw_result_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=text("NOW()"),
    )


class AsrUtteranceModel(Base):
    __tablename__ = "asr_utterances"
    __table_args__ = (
        UniqueConstraint("task_id", "seq", name="uq_asr_utterance_task_seq"),
        {"schema": "public"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column("x_text", Text, nullable=False)
    speaker: Mapped[str | None] = mapped_column(String(64), nullable=True)
    start_time: Mapped[int] = mapped_column(Integer, nullable=False)
    end_time: Mapped[int] = mapped_column(Integer, nullable=False)
    additions_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=text("NOW()"),
    )
