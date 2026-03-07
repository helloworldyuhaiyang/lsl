from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, SmallInteger, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lsl.core.db import Base


class UtterancesRevisionModel(Base):
    __tablename__ = "utterances_revisions"
    __table_args__ = {"schema": "public"}

    revision_id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("public.sessions.session_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    task_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("public.tasks.task_id", ondelete="RESTRICT"),
        nullable=False,
    )
    user_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[int] = mapped_column("x_status", SmallInteger, nullable=False, server_default=text("0"))
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    item_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
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

    items: Mapped[list["UtterancesRevisionItemModel"]] = relationship(
        back_populates="revision",
        cascade="all, delete-orphan",
        order_by="UtterancesRevisionItemModel.utterance_seq",
    )


class UtterancesRevisionItemModel(Base):
    __tablename__ = "utterances_revision_items"
    __table_args__ = {"schema": "public"}

    item_id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    revision_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("public.utterances_revisions.revision_id", ondelete="CASCADE"),
        nullable=False,
    )
    task_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("public.tasks.task_id", ondelete="RESTRICT"),
        nullable=False,
    )
    utterance_seq: Mapped[int] = mapped_column(Integer, nullable=False)
    speaker: Mapped[str | None] = mapped_column(String(64), nullable=True)
    start_time: Mapped[int] = mapped_column(Integer, nullable=False)
    end_time: Mapped[int] = mapped_column(Integer, nullable=False)
    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_text: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_cue: Mapped[str | None] = mapped_column(Text, nullable=True)
    draft_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    draft_cue: Mapped[str | None] = mapped_column(Text, nullable=True)
    score: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    issue_tags_json: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    explanations_json: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
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

    revision: Mapped[UtterancesRevisionModel] = relationship(back_populates="items")
