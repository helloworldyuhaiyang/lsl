from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
from typing import Any, Protocol


class JobStatus(IntEnum):
    QUEUED = 0
    RUNNING = 1
    COMPLETED = 2
    FAILED = 3
    CANCELED = 4


JOB_STATUS_NAME_MAP: dict[int, str] = {
    JobStatus.QUEUED: "queued",
    JobStatus.RUNNING: "running",
    JobStatus.COMPLETED: "completed",
    JobStatus.FAILED: "failed",
    JobStatus.CANCELED: "canceled",
}


def job_status_to_name(status_code: int) -> str:
    return JOB_STATUS_NAME_MAP.get(status_code, "unknown")


@dataclass(frozen=True, slots=True)
class JobRunResult:
    status: JobStatus
    progress: int | None = None
    next_run_at: datetime | None = None
    result: dict[str, Any] | None = None
    error_code: str | None = None
    error_message: str | None = None
    entity_type: str | None = None
    entity_id: str | None = None


@dataclass(frozen=True, slots=True)
class JobData:
    job_id: str
    job_type: str
    status: int
    status_name: str
    entity_type: str | None = None
    entity_id: str | None = None
    priority: int = 0
    progress: int = 0
    attempts: int = 0
    max_attempts: int = 3
    payload: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] | None = None
    error_code: str | None = None
    error_message: str | None = None
    locked_by: str | None = None
    locked_until: datetime | None = None
    next_run_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class JobHandler(Protocol):
    job_type: str

    def run(self, job: JobData) -> JobRunResult:
        ...
