from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field, field_validator

from lsl.modules.job.types import JobData


T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    code: int = 0
    message: str = "successful"
    data: T


class CreateJobRequest(BaseModel):
    job_type: str = Field(..., min_length=1, max_length=64)
    entity_type: str | None = Field(default=None, max_length=64)
    entity_id: str | None = Field(default=None, max_length=128)
    payload: dict[str, Any] = Field(default_factory=dict)
    priority: int = Field(default=0)
    max_attempts: int = Field(default=3, ge=1, le=100)
    next_run_at: datetime | None = None

    @field_validator("job_type", "entity_type", "entity_id")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("value cannot be blank")
        return normalized


class JobListResponseData(BaseModel):
    items: list[JobData]


class RunDueJobsRequest(BaseModel):
    limit: int = Field(default=10, ge=1, le=100)
    worker_id: str | None = Field(default=None, max_length=128)


class RunJobsResponseData(BaseModel):
    items: list[JobData]
