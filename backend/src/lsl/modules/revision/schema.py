from __future__ import annotations

from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, Field, field_validator

from lsl.modules.revision.types import status_code_to_name


T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    code: int = 0
    message: str = "successful"
    data: T


class CreateRevisionRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=64)
    user_prompt: str | None = Field(default=None, max_length=4000)
    force: bool = False

    @field_validator("session_id")
    @classmethod
    def normalize_session_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("session_id is required")
        return normalized

    @field_validator("user_prompt")
    @classmethod
    def normalize_user_prompt(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class UpdateRevisionItemRequest(BaseModel):
    draft_text: str | None = Field(default=None, max_length=8000)
    draft_cue: str | None = Field(default=None, max_length=1000)

    @field_validator("draft_text")
    @classmethod
    def normalize_draft_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("draft_cue")
    @classmethod
    def normalize_draft_cue(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class RevisionItemData(BaseModel):
    item_id: str
    revision_id: str
    task_id: str
    utterance_seq: int
    speaker: str | None = None
    start_time: int
    end_time: int
    original_text: str
    suggested_text: str
    suggested_cue: str | None = None
    draft_text: str | None = None
    draft_cue: str | None = None
    score: int
    issue_tags: list[str]
    explanations: list[str]
    created_at: datetime
    updated_at: datetime


class RevisionData(BaseModel):
    revision_id: str
    session_id: str
    task_id: str
    user_prompt: str | None = None
    status: int
    status_name: str
    error_code: str | None = None
    error_message: str | None = None
    item_count: int
    created_at: datetime
    updated_at: datetime
    items: list[RevisionItemData]

    @classmethod
    def build(
        cls,
        *,
        revision_id: str,
        session_id: str,
        task_id: str,
        user_prompt: str | None,
        status: int,
        error_code: str | None,
        error_message: str | None,
        item_count: int,
        created_at: datetime,
        updated_at: datetime,
        items: list[RevisionItemData],
    ) -> "RevisionData":
        return cls(
            revision_id=revision_id,
            session_id=session_id,
            task_id=task_id,
            user_prompt=user_prompt,
            status=status,
            status_name=status_code_to_name(status),
            error_code=error_code,
            error_message=error_message,
            item_count=item_count,
            created_at=created_at,
            updated_at=updated_at,
            items=items,
        )
