from __future__ import annotations

from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, Field, field_validator

from lsl.modules.tts.types import status_code_to_name


T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    code: int = 0
    message: str = "successful"
    data: T


class TtsSpeakerData(BaseModel):
    speaker_id: str
    name: str
    language: str | None = None
    gender: str | None = None
    style: str | None = None
    description: str | None = None


class TtsSpeakerListData(BaseModel):
    items: list[TtsSpeakerData]


class TtsSpeakerMappingData(BaseModel):
    conversation_speaker: str
    provider_speaker_id: str


class TtsSettingsData(BaseModel):
    session_id: str
    format: str
    emotion_scale: float
    speech_rate: float
    loudness_rate: float
    speaker_mappings: list[TtsSpeakerMappingData]


class UpdateTtsSettingsRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=64)
    format: str = Field(..., min_length=1, max_length=16)
    emotion_scale: float = Field(..., gt=0)
    speech_rate: float = Field(..., gt=0)
    loudness_rate: float = Field(..., gt=0)
    speaker_mappings: list[TtsSpeakerMappingData] = Field(default_factory=list)

    @field_validator("session_id")
    @classmethod
    def normalize_session_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("session_id is required")
        return normalized

    @field_validator("format")
    @classmethod
    def normalize_format(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("format is required")
        return normalized


class GenerateTtsItemRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=64)
    content: str = Field(..., min_length=1, max_length=12000)
    force: bool = False

    @field_validator("session_id")
    @classmethod
    def normalize_session_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("session_id is required")
        return normalized

    @field_validator("content")
    @classmethod
    def normalize_content(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("content is required")
        return normalized


class CreateTtsSynthesisRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=64)
    force: bool = False

    @field_validator("session_id")
    @classmethod
    def normalize_session_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("session_id is required")
        return normalized


class TtsSynthesisItemData(BaseModel):
    item_id: str
    conversation_speaker: str | None = None
    provider_speaker_id: str
    content: str
    plain_text: str
    cue_texts: list[str]
    content_hash: str
    duration_ms: int | None = None
    status: int
    status_name: str

    @classmethod
    def build(
        cls,
        *,
        item_id: str,
        conversation_speaker: str | None,
        provider_speaker_id: str,
        content: str,
        plain_text: str,
        cue_texts: list[str],
        content_hash: str,
        duration_ms: int | None,
        status: int,
    ) -> "TtsSynthesisItemData":
        return cls(
            item_id=item_id,
            conversation_speaker=conversation_speaker,
            provider_speaker_id=provider_speaker_id,
            content=content,
            plain_text=plain_text,
            cue_texts=cue_texts,
            content_hash=content_hash,
            duration_ms=duration_ms,
            status=status,
            status_name=status_code_to_name(status),
        )


class TtsSynthesisData(BaseModel):
    synthesis_id: str
    session_id: str
    provider: str
    full_asset_url: str | None = None
    full_duration_ms: int | None = None
    item_count: int
    completed_item_count: int
    failed_item_count: int
    status: int
    status_name: str
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
    items: list[TtsSynthesisItemData]

    @classmethod
    def build(
        cls,
        *,
        synthesis_id: str,
        session_id: str,
        provider: str,
        full_asset_url: str | None,
        full_duration_ms: int | None,
        item_count: int,
        completed_item_count: int,
        failed_item_count: int,
        status: int,
        error_code: str | None,
        error_message: str | None,
        created_at: datetime,
        updated_at: datetime,
        items: list[TtsSynthesisItemData],
    ) -> "TtsSynthesisData":
        return cls(
            synthesis_id=synthesis_id,
            session_id=session_id,
            provider=provider,
            full_asset_url=full_asset_url,
            full_duration_ms=full_duration_ms,
            item_count=item_count,
            completed_item_count=completed_item_count,
            failed_item_count=failed_item_count,
            status=status,
            status_name=status_code_to_name(status),
            error_code=error_code,
            error_message=error_message,
            created_at=created_at,
            updated_at=updated_at,
            items=items,
        )
