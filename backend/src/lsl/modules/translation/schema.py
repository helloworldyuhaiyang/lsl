from __future__ import annotations

from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, Field, field_validator

from lsl.modules.translation.types import translation_item_status_to_name, translation_status_to_name

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    code: int = 0
    message: str = "successful"
    data: T


class CreateTranslationRequest(BaseModel):
    source_type: str = Field(..., min_length=1, max_length=32)
    source_entity_id: str = Field(..., min_length=1, max_length=128)
    session_id: str | None = Field(default=None, max_length=64)
    target_language: str = Field(default="zh-CN", min_length=2, max_length=16)
    force: bool = False

    @field_validator("source_type", "source_entity_id", "target_language")
    @classmethod
    def normalize_required(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value is required")
        return normalized

    @field_validator("session_id")
    @classmethod
    def normalize_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class TranslationItemData(BaseModel):
    item_id: str
    translation_id: str
    source_item_key: str
    source_seq: int | None = None
    speaker: str | None = None
    start_time: int | None = None
    end_time: int | None = None
    source_text: str
    source_text_hash: str
    translated_text: str | None = None
    status: int
    status_name: str
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class TranslationData(BaseModel):
    translation_id: str
    session_id: str | None = None
    source_type: str
    source_entity_id: str
    source_language: str | None = None
    target_language: str
    job_id: str | None = None
    provider: str
    model: str | None = None
    status: int
    status_name: str
    item_count: int
    completed_count: int
    stale_count: int
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
    items: list[TranslationItemData] = Field(default_factory=list)

    @classmethod
    def from_row(cls, row: dict) -> "TranslationData":
        status = int(row["status"])
        return cls(
            translation_id=str(row["translation_id"]),
            session_id=row.get("session_id"),
            source_type=str(row["source_type"]),
            source_entity_id=str(row["source_entity_id"]),
            source_language=row.get("source_language"),
            target_language=str(row["target_language"]),
            job_id=row.get("job_id"),
            provider=str(row["provider"]),
            model=row.get("model"),
            status=status,
            status_name=translation_status_to_name(status),
            item_count=int(row["item_count"]),
            completed_count=int(row["completed_count"]),
            stale_count=int(row["stale_count"]),
            error_code=row.get("error_code"),
            error_message=row.get("error_message"),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            items=[
                TranslationItemData(
                    item_id=str(item["item_id"]),
                    translation_id=str(item["translation_id"]),
                    source_item_key=str(item["source_item_key"]),
                    source_seq=item.get("source_seq"),
                    speaker=item.get("speaker"),
                    start_time=item.get("start_time"),
                    end_time=item.get("end_time"),
                    source_text=str(item["source_text"]),
                    source_text_hash=str(item["source_text_hash"]),
                    translated_text=item.get("translated_text"),
                    status=int(item["status"]),
                    status_name=translation_item_status_to_name(int(item["status"])),
                    error_code=item.get("error_code"),
                    error_message=item.get("error_message"),
                    created_at=item["created_at"],
                    updated_at=item["updated_at"],
                )
                for item in row.get("items", [])
            ],
        )
