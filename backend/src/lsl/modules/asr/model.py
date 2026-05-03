from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Index, Integer, SmallInteger, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from lsl.core.db import Base
from lsl.core.sql_types import UUIDHexString


class AsrRecognitionModel(Base):
    __tablename__ = "asr_recognitions"
    __table_args__ = (
        Index("idx_asr_recognitions_transcript_id", "transcript_id"),
        Index("idx_asr_recognitions_status_created_at", "x_status", "created_at"),
        Index("idx_asr_recognitions_object_key", "object_key"),
    )

    recognition_id: Mapped[str] = mapped_column(UUIDHexString(), primary_key=True)
    transcript_id: Mapped[str] = mapped_column(UUIDHexString(), nullable=False)
    job_id: Mapped[str | None] = mapped_column(UUIDHexString(), nullable=True)
    object_key: Mapped[str] = mapped_column(Text, nullable=False)
    audio_url: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str | None] = mapped_column("x_language", String(16), nullable=True)
    provider: Mapped[str] = mapped_column("x_provider", String(32), nullable=False)
    status: Mapped[int] = mapped_column("x_status", SmallInteger, nullable=False, server_default=text("0"))
    provider_request_id: Mapped[str | None] = mapped_column("x_provider_request_id", String(128), nullable=True)
    provider_resource_id: Mapped[str | None] = mapped_column("x_provider_resource_id", String(128), nullable=True)
    x_tt_logid: Mapped[str | None] = mapped_column(String(255), nullable=True)
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
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        server_default=text("CURRENT_TIMESTAMP"),
    )
