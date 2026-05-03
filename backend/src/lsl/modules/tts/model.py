from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Index, Integer, Numeric, SmallInteger, String, Text, text
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship

from lsl.core.db import Base
from lsl.core.sql_types import JSONString, UUIDHexString


class SessionTtsSettingsModel(Base):
    __tablename__ = "session_tts_settings"

    session_id: Mapped[str] = mapped_column(UUIDHexString(), primary_key=True)
    format: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'mp3'"))
    emotion_scale: Mapped[float] = mapped_column(Numeric(), nullable=False, server_default=text("4.0"))
    speech_rate: Mapped[float] = mapped_column(Numeric(), nullable=False, server_default=text("0.0"))
    loudness_rate: Mapped[float] = mapped_column(Numeric(), nullable=False, server_default=text("0.0"))
    speaker_mappings_json: Mapped[list[dict[str, str]]] = mapped_column(
        JSONString(),
        nullable=False,
        default=list,
        server_default=text("'[]'"),
    )
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


class SpeechSynthesisModel(Base):
    __tablename__ = "speech_syntheses"
    __table_args__ = (
        Index("idx_speech_syntheses_session_created_at", "session_id", "created_at"),
    )

    synthesis_id: Mapped[str] = mapped_column(UUIDHexString(), primary_key=True)
    session_id: Mapped[str] = mapped_column(UUIDHexString(), nullable=False, unique=True)
    provider: Mapped[str] = mapped_column("x_provider", String(32), nullable=False)
    full_content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    full_asset_object_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    full_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    item_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    completed_item_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    failed_item_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    status: Mapped[int] = mapped_column("x_status", SmallInteger, nullable=False, server_default=text("0"))
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
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

    items: Mapped[list["SpeechSynthesisItemModel"]] = relationship(
        back_populates="synthesis",
        cascade="all, delete-orphan",
        order_by=lambda: (
            SpeechSynthesisItemModel.source_seq_start,
            SpeechSynthesisItemModel.source_seq_end,
        ),
        primaryjoin=lambda: SpeechSynthesisModel.synthesis_id == foreign(SpeechSynthesisItemModel.synthesis_id),
        foreign_keys=lambda: [SpeechSynthesisItemModel.synthesis_id],
    )


class SpeechSynthesisItemModel(Base):
    __tablename__ = "speech_synthesis_items"
    __table_args__ = (
        Index(
            "idx_speech_synthesis_items_seq_span",
            "synthesis_id",
            "source_seq_start",
            "source_seq_end",
        ),
    )

    tts_item_id: Mapped[str] = mapped_column(UUIDHexString(), primary_key=True)
    synthesis_id: Mapped[str] = mapped_column(UUIDHexString(), nullable=False)
    source_item_id: Mapped[str] = mapped_column(UUIDHexString(), nullable=False)
    source_seq_start: Mapped[int] = mapped_column(Integer, nullable=False)
    source_seq_end: Mapped[int] = mapped_column(Integer, nullable=False)
    source_seqs: Mapped[list[int]] = mapped_column(
        JSONString(),
        nullable=False,
        default=list,
        server_default=text("'[]'"),
    )
    conversation_speaker: Mapped[str | None] = mapped_column(String(64), nullable=True)
    provider_speaker_id: Mapped[str] = mapped_column(String(128), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    plain_text: Mapped[str] = mapped_column(Text, nullable=False)
    cue_texts: Mapped[list[str]] = mapped_column(
        JSONString(),
        nullable=False,
        default=list,
        server_default=text("'[]'"),
    )
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[int] = mapped_column("x_status", SmallInteger, nullable=False, server_default=text("0"))
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
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

    synthesis: Mapped[SpeechSynthesisModel] = relationship(
        back_populates="items",
        primaryjoin=lambda: foreign(SpeechSynthesisItemModel.synthesis_id) == SpeechSynthesisModel.synthesis_id,
        foreign_keys=lambda: [SpeechSynthesisItemModel.synthesis_id],
    )
