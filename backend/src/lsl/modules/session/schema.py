from __future__ import annotations

from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator


T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    code: int = 0
    message: str = "successful"
    data: T


class CreateSessionRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    language: str | None = Field(default=None, max_length=16)
    f_type: int = Field(default=1, ge=1, le=2)
    asset_object_key: str | None = Field(default=None, max_length=1024)
    current_transcript_id: str | None = Field(default=None, max_length=64)

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("title is required")
        return normalized

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("asset_object_key")
    @classmethod
    def normalize_asset_object_key(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lstrip("/")
        return normalized or None

    @field_validator("current_transcript_id")
    @classmethod
    def normalize_current_transcript_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class UpdateSessionRequest(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    language: str | None = Field(default=None, max_length=16)
    f_type: int | None = Field(default=None, ge=1, le=2)
    asset_object_key: str | None = Field(default=None, max_length=1024)
    current_transcript_id: str | None = Field(default=None, max_length=64)

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("title cannot be empty")
        return normalized

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("asset_object_key")
    @classmethod
    def normalize_asset_object_key(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lstrip("/")
        return normalized or None

    @field_validator("current_transcript_id")
    @classmethod
    def normalize_current_transcript_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class SessionSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    session_id: str
    title: str
    description: str | None = None
    language: str | None = None
    f_type: int
    asset_object_key: str | None = None
    current_transcript_id: str | None = None
    created_at: datetime
    updated_at: datetime


class AssetSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    filename: str | None = None
    object_key: str
    category: str
    entity_id: str
    content_type: str | None = None
    file_size: int | None = None
    etag: str | None = None
    upload_status: int
    created_at: datetime
    asset_url: str


class TranscriptSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    transcript_id: str
    source_type: str
    source_entity_id: str | None = None
    duration_ms: int | None = None
    duration_sec: float | None = None
    status: int
    status_name: str
    language: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class SessionData(BaseModel):
    session: SessionSchema
    asset: AssetSchema | None = None
    transcript: TranscriptSchema | None = None


class SessionListResponseData(BaseModel):
    items: list[SessionData]
