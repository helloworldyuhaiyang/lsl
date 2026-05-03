from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Index, Integer, SmallInteger, String, Text, text
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship

from lsl.core.db import Base
from lsl.core.sql_types import JSONString, UUIDHexString


class UtterancesRevisionModel(Base):
    __tablename__ = "revision_revisions"
    __table_args__ = (
        Index("idx_revision_revisions_session_id", "session_id"),
    )

    revision_id: Mapped[str] = mapped_column(UUIDHexString(), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        UUIDHexString(),
        nullable=False,
    )
    transcript_id: Mapped[str] = mapped_column(
        UUIDHexString(),
        nullable=False,
    )
    # Active generic job for the current revise run; newer runs replace this value.
    job_id: Mapped[str | None] = mapped_column(UUIDHexString(), nullable=True)
    user_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[int] = mapped_column("x_status", SmallInteger, nullable=False, server_default=text("0"))
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    item_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
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

    items: Mapped[list["UtterancesRevisionItemModel"]] = relationship(
        back_populates="revision",
        cascade="all, delete-orphan",
        order_by=lambda: (
            UtterancesRevisionItemModel.source_seq_start,
            UtterancesRevisionItemModel.source_seq_end,
        ),
        primaryjoin=lambda: UtterancesRevisionModel.revision_id
        == foreign(UtterancesRevisionItemModel.revision_id),
        foreign_keys=lambda: [UtterancesRevisionItemModel.revision_id],
    )


class UtterancesRevisionItemModel(Base):
    __tablename__ = "revision_items"
    __table_args__ = (
        Index(
            "idx_revision_items_revision_seq_span",
            "revision_id",
            "source_seq_start",
            "source_seq_end",
        ),
        Index(
            "idx_revision_items_transcript_seq_span",
            "transcript_id",
            "source_seq_start",
            "source_seq_end",
        ),
    )

    item_id: Mapped[str] = mapped_column(UUIDHexString(), primary_key=True)
    revision_id: Mapped[str] = mapped_column(
        UUIDHexString(),
        nullable=False,
    )
    transcript_id: Mapped[str] = mapped_column(
        UUIDHexString(),
        nullable=False,
    )
    source_seq_start: Mapped[int] = mapped_column(Integer, nullable=False)
    source_seq_end: Mapped[int] = mapped_column(Integer, nullable=False)
    source_seq_count: Mapped[int] = mapped_column(Integer, nullable=False)
    source_seqs: Mapped[list[int]] = mapped_column(
        JSONString(),
        nullable=False,
        default=list,
        server_default=text("'[]'"),
    )
    speaker: Mapped[str | None] = mapped_column(String(64), nullable=True)
    start_time: Mapped[int] = mapped_column(Integer, nullable=False)
    end_time: Mapped[int] = mapped_column(Integer, nullable=False)
    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_text: Mapped[str] = mapped_column(Text, nullable=False)
    draft_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    score: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    issue_tags: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default=text("''"))
    explanations: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default=text("''"))
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

    revision: Mapped[UtterancesRevisionModel] = relationship(
        back_populates="items",
        primaryjoin=lambda: foreign(UtterancesRevisionItemModel.revision_id)
        == UtterancesRevisionModel.revision_id,
        foreign_keys=lambda: [UtterancesRevisionItemModel.revision_id],
    )
