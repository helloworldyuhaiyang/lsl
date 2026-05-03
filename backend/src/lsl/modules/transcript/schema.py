from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field


T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    code: int = 0
    message: str = "successful"
    data: T


class TranscriptUtteranceData(BaseModel):
    seq: int
    text: str
    speaker: str | None = None
    start_time: int
    end_time: int
    additions: dict[str, Any] = Field(default_factory=dict)


class TranscriptData(BaseModel):
    transcript_id: str
    source_type: str
    source_entity_id: str | None = None
    language: str | None = None
    duration_ms: int | None = None
    duration_sec: float | None = None
    full_text: str | None = None
    raw_result: dict[str, Any] | None = None
    status: int
    status_name: str
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
    utterances: list[TranscriptUtteranceData] = Field(default_factory=list)

    @classmethod
    def from_row(cls, row: dict[str, Any], *, include_raw: bool = False) -> TranscriptData:
        duration_ms = row.get("duration_ms")
        duration_ms_int = int(duration_ms) if duration_ms is not None else None
        return cls(
            transcript_id=str(row["transcript_id"]),
            source_type=str(row["source_type"]),
            source_entity_id=row.get("source_entity_id"),
            language=row.get("language"),
            duration_ms=duration_ms_int,
            duration_sec=(duration_ms_int / 1000) if duration_ms_int is not None else None,
            full_text=row.get("full_text"),
            raw_result=row.get("raw_result") if include_raw else None,
            status=int(row["status"]),
            status_name=str(row["status_name"]),
            error_code=row.get("error_code"),
            error_message=row.get("error_message"),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            utterances=[
                TranscriptUtteranceData(
                    seq=int(item["seq"]),
                    text=item["text"],
                    speaker=item.get("speaker"),
                    start_time=int(item["start_time"]),
                    end_time=int(item["end_time"]),
                    additions=item.get("additions") or {},
                )
                for item in row.get("utterances", [])
            ],
        )


class TranscriptListResponseData(BaseModel):
    items: list[TranscriptData]


class TranscriptUtteranceListResponseData(BaseModel):
    items: list[TranscriptUtteranceData]
