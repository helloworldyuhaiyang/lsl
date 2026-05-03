from __future__ import annotations

from enum import IntEnum
from typing import Any

from pydantic import BaseModel, Field


class TranscriptStatus(IntEnum):
    PENDING = 0
    COMPLETED = 1
    FAILED = 2


TRANSCRIPT_STATUS_NAME_MAP: dict[int, str] = {
    TranscriptStatus.PENDING: "pending",
    TranscriptStatus.COMPLETED: "completed",
    TranscriptStatus.FAILED: "failed",
}


def transcript_status_to_name(status_code: int) -> str:
    return TRANSCRIPT_STATUS_NAME_MAP.get(status_code, "unknown")


class TranscriptUtterance(BaseModel):
    seq: int = Field(..., ge=0)
    text: str = Field(..., min_length=1)
    speaker: str | None = None
    start_time: int = Field(..., ge=0)
    end_time: int = Field(..., ge=0)
    additions: dict[str, Any] = Field(default_factory=dict)
