from __future__ import annotations

from enum import Enum, IntEnum
from typing import Any, Protocol

from pydantic import BaseModel, Field


class AsrRecognitionStatus(IntEnum):
    PENDING = 0
    SUBMITTED = 1
    PROCESSING = 2
    COMPLETED = 3
    FAILED = 4


ASR_RECOGNITION_STATUS_NAME_MAP: dict[int, str] = {
    AsrRecognitionStatus.PENDING: "pending",
    AsrRecognitionStatus.SUBMITTED: "submitted",
    AsrRecognitionStatus.PROCESSING: "processing",
    AsrRecognitionStatus.COMPLETED: "completed",
    AsrRecognitionStatus.FAILED: "failed",
}


def asr_recognition_status_to_name(status_code: int) -> str:
    return ASR_RECOGNITION_STATUS_NAME_MAP.get(status_code, "unknown")


class AsrProvider(Protocol):
    def submit(self, req: AsrSubmitRequest) -> AsrJobRef:
        ...

    def query(self, ref: AsrJobRef) -> AsrQueryResult:
        ...


class AsrJobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class AsrSubmitRequest(BaseModel):
    recognition_id: str
    audio_url: str
    language: str | None = None


class AsrJobRef(BaseModel):
    recognition_id: str
    provider: str
    provider_request_id: str
    provider_resource_id: str | None = None
    x_tt_logid: str | None = None


class AsrUtterance(BaseModel):
    seq: int = Field(..., ge=0)
    text: str = Field(..., min_length=1)
    speaker: str | None = None
    start_time: int = Field(..., ge=0)
    end_time: int = Field(..., ge=0)
    additions: dict[str, Any] = Field(default_factory=dict)


class AsrQueryResult(BaseModel):
    status: AsrJobStatus
    provider_status_code: str | None = None
    provider_message: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    duration_ms: int | None = None
    full_text: str | None = None
    utterances: list[AsrUtterance] = Field(default_factory=list)
    raw_result: dict[str, Any] | None = None
    x_tt_logid: str | None = None


class NoopAsrProvider:
    provider_name = "noop"

    def submit(self, req: AsrSubmitRequest) -> AsrJobRef:
        raise NotImplementedError("ASR provider is not implemented")

    def query(self, ref: AsrJobRef) -> AsrQueryResult:
        raise NotImplementedError("ASR provider is not implemented")
