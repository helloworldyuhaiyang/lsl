from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field, field_validator

from lsl.modules.revision.schema import RevisionData
from lsl.modules.session.schema import SessionData


T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    code: int = 0
    message: str = "successful"
    data: T


class GenerateScriptSessionRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    language: str | None = Field(default="en-US", max_length=16)
    prompt: str = Field(..., min_length=1, max_length=4000)
    turn_count: int = Field(default=8, ge=2, le=24)
    speaker_count: int = Field(default=2, ge=2, le=4)
    difficulty: str | None = Field(default="intermediate", max_length=32)
    cue_style: str | None = Field(default="自然口语、便于 TTS 演绎", max_length=200)
    must_include: list[str] = Field(default_factory=list, max_length=12)

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

    @field_validator("language")
    @classmethod
    def normalize_language(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("prompt")
    @classmethod
    def normalize_prompt(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("prompt is required")
        return normalized

    @field_validator("difficulty")
    @classmethod
    def normalize_difficulty(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("cue_style")
    @classmethod
    def normalize_cue_style(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("must_include")
    @classmethod
    def normalize_must_include(cls, value: list[str]) -> list[str]:
        result: list[str] = []
        for item in value:
            normalized = str(item).strip()
            if normalized:
                result.append(normalized)
        return result


class GenerateScriptSessionData(BaseModel):
    session: SessionData
    revision: RevisionData
