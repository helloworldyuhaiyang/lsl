from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session as OrmSession
from sqlalchemy.orm import sessionmaker

from lsl.core.db import Base
from lsl.modules.job.repo import JobRepository
from lsl.modules.job.service import JobService
from lsl.modules.job.types import JobData, JobRunResult, JobStatus


def _build_service() -> JobService:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, class_=OrmSession)
    return JobService(repository=JobRepository(factory), lock_ttl_seconds=30)


@dataclass
class CompleteHandler:
    job_type: str = "test.complete"

    def run(self, job: JobData) -> JobRunResult:
        return JobRunResult(
            status=JobStatus.COMPLETED,
            progress=100,
            result={"ok": True, "input": job.payload.get("value")},
            entity_type="test_entity",
            entity_id="entity-1",
        )


class PollingHandler:
    job_type = "test.poll"

    def __init__(self) -> None:
        self.calls = 0

    def run(self, job: JobData) -> JobRunResult:
        self.calls += 1
        if self.calls == 1:
            return JobRunResult(
                status=JobStatus.RUNNING,
                progress=50,
                next_run_at=datetime.now(timezone.utc) + timedelta(seconds=60),
            )
        return JobRunResult(status=JobStatus.COMPLETED, result={"done": True})


def test_job_service_runs_registered_handler_to_completion() -> None:
    service = _build_service()
    service.register_handler(CompleteHandler())

    job = service.create_job(job_type="test.complete", payload={"value": 42})
    completed = service.run_job(job_id=job.job_id, worker_id="test-worker")

    assert completed.status == int(JobStatus.COMPLETED)
    assert completed.status_name == "completed"
    assert completed.progress == 100
    assert completed.result == {"ok": True, "input": 42}
    assert completed.entity_type == "test_entity"
    assert completed.entity_id == "entity-1"
    assert completed.locked_by is None


def test_job_service_reschedules_running_job() -> None:
    service = _build_service()
    handler = PollingHandler()
    service.register_handler(handler)

    job = service.create_job(job_type="test.poll")
    running = service.run_job(job_id=job.job_id, worker_id="test-worker")

    assert running.status == int(JobStatus.RUNNING)
    assert running.progress == 50
    assert running.next_run_at is not None

    due_items = service.run_due_jobs(limit=10, worker_id="test-worker")

    assert due_items == []
    assert handler.calls == 1


def test_job_service_marks_missing_handler_as_failed() -> None:
    service = _build_service()

    job = service.create_job(job_type="test.missing")
    failed = service.run_job(job_id=job.job_id, worker_id="test-worker")

    assert failed.status == int(JobStatus.FAILED)
    assert failed.error_code == "JOB_HANDLER_NOT_FOUND"
