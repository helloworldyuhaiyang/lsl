from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from lsl.task.status import status_code_to_name


class CreateTaskRequest(BaseModel):
    object_key: str = Field(..., min_length=1, max_length=1024)
    audio_url: str = Field(..., min_length=1, max_length=4096)
    language: str | None = Field(default=None, max_length=16)

    @field_validator("object_key")
    @classmethod
    def normalize_object_key(cls, value: str) -> str:
        normalized = value.strip().lstrip("/")
        if not normalized:
            raise ValueError("object_key is required")
        return normalized

    @field_validator("audio_url")
    @classmethod
    def normalize_audio_url(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("audio_url is required")
        return normalized


class TaskData(BaseModel):
    task_id: str
    object_key: str
    audio_url: str | None = None
    status: int
    status_name: str
    language: str | None = None
    provider: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> TaskData:
        status_code = int(row["status"])
        return cls(
            task_id=str(row["task_id"]),
            object_key=row["object_key"],
            audio_url=row.get("audio_url"),
            status=status_code,
            status_name=status_code_to_name(status_code),
            language=row.get("language"),
            provider=row.get("provider"),
            error_code=row.get("error_code"),
            error_message=row.get("error_message"),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


class TaskListResponseData(BaseModel):
    items: list[TaskData]


class TaskTranscriptUtterance(BaseModel):
    seq: int = Field(..., ge=0)
    text: str
    speaker: str | None = None
    start_time: int = Field(..., ge=0)
    end_time: int = Field(..., ge=0)
    additions: dict[str, Any] = Field(default_factory=dict)


class TaskTranscriptData(BaseModel):
    task_id: str
    duration_ms: int | None = None
    full_text: str | None = None
    utterances: list[TaskTranscriptUtterance]
    raw_result: dict[str, Any] | None = None
