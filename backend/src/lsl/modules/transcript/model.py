from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Index, Integer, SmallInteger, String, Text, UniqueConstraint, text as sql_text
from sqlalchemy.orm import Mapped, mapped_column

from lsl.core.db import Base
from lsl.core.sql_types import JSONString, UUIDHexString


class TranscriptModel(Base):
    __tablename__ = "transcript_transcripts"
    __table_args__ = (
        Index("idx_transcript_transcripts_source", "source_type", "source_entity_id"),
        Index("idx_transcript_transcripts_status_created_at", "x_status", "created_at"),
    )

    transcript_id: Mapped[str] = mapped_column(UUIDHexString(), primary_key=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_entity_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    language: Mapped[str | None] = mapped_column("x_language", String(16), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    full_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_result_json: Mapped[dict | None] = mapped_column(JSONString(), nullable=True)
    status: Mapped[int] = mapped_column("x_status", SmallInteger, nullable=False, server_default=sql_text("0"))
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=sql_text("CURRENT_TIMESTAMP"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        server_default=sql_text("CURRENT_TIMESTAMP"),
    )


class TranscriptUtteranceModel(Base):
    __tablename__ = "transcript_utterances"
    __table_args__ = (
        UniqueConstraint("transcript_id", "seq", name="uq_transcript_utterance_transcript_seq"),
        Index("idx_transcript_utterances_transcript_id", "transcript_id", "seq"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    transcript_id: Mapped[str] = mapped_column(UUIDHexString(), nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column("x_text", Text, nullable=False)
    speaker: Mapped[str | None] = mapped_column(String(64), nullable=True)
    start_time: Mapped[int] = mapped_column(Integer, nullable=False)
    end_time: Mapped[int] = mapped_column(Integer, nullable=False)
    additions_json: Mapped[dict] = mapped_column(
        JSONString(),
        nullable=False,
        default=dict,
        server_default=sql_text("'{}'"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=sql_text("CURRENT_TIMESTAMP"),
    )
