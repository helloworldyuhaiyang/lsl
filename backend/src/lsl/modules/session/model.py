from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, SmallInteger, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from lsl.core.db import Base
from lsl.core.sql_types import UUIDHexString


class SessionModel(Base):
    __tablename__ = "sessions"

    session_id: Mapped[str] = mapped_column(UUIDHexString(), primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column("f_desc", Text, nullable=True)
    language: Mapped[str | None] = mapped_column("f_language", String(16), nullable=True)
    f_type: Mapped[int] = mapped_column("f_type", SmallInteger, nullable=False, server_default=text("1"))
    asset_object_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_task_id: Mapped[str | None] = mapped_column(UUIDHexString(), nullable=True)
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
