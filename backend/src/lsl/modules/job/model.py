from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Index, Integer, SmallInteger, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from lsl.core.db import Base
from lsl.core.sql_types import JSONString, UUIDHexString


class JobModel(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        Index("idx_jobs_status_next_run_at", "x_status", "next_run_at"),
        Index("idx_jobs_type_status_next_run_at", "job_type", "x_status", "next_run_at"),
        Index("idx_jobs_entity", "entity_type", "entity_id"),
        Index("idx_jobs_created_at", "created_at"),
    )

    job_id: Mapped[str] = mapped_column(UUIDHexString(), primary_key=True)
    job_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[int] = mapped_column("x_status", SmallInteger, nullable=False, server_default=text("0"))
    entity_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    progress: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("3"))
    payload_json: Mapped[dict] = mapped_column(
        JSONString(),
        nullable=False,
        default=dict,
        server_default=text("'{}'"),
    )
    result_json: Mapped[dict | None] = mapped_column(JSONString(), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    locked_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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
