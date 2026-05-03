from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session as OrmSession
from sqlalchemy.orm import sessionmaker

from lsl.core.db import Base
from lsl.modules.asr.repo import AsrRepository
from lsl.modules.asr.service import AsrJobHandler, AsrService
from lsl.modules.asr.types import AsrJobRef, AsrJobStatus, AsrQueryResult, AsrRecognitionStatus, AsrSubmitRequest
from lsl.modules.asr.providers.fake_asr import FakeAsrProvider
from lsl.modules.job.repo import JobRepository
from lsl.modules.job.service import JobService
from lsl.modules.job.types import JobStatus
from lsl.modules.transcript.repo import TranscriptRepository
from lsl.modules.transcript.service import TranscriptService
from lsl.modules.transcript.types import TranscriptStatus


class FailingAsrProvider:
    provider_name = "failing"

    def submit(self, req: AsrSubmitRequest) -> AsrJobRef:
        return AsrJobRef(
            recognition_id=req.recognition_id,
            provider=self.provider_name,
            provider_request_id=f"req-{req.recognition_id}",
        )

    def query(self, ref: AsrJobRef) -> AsrQueryResult:
        return AsrQueryResult(
            status=AsrJobStatus.FAILED,
            provider_status_code="500",
            provider_message="failed by fixture",
            error_code="FIXTURE_FAILED",
            error_message="ASR fixture failed",
        )


def _build_services() -> tuple[AsrService, JobService, TranscriptService]:
    return _build_services_with_provider(FakeAsrProvider())


def _build_services_with_provider(provider) -> tuple[AsrService, JobService, TranscriptService]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, class_=OrmSession)
    job_service = JobService(repository=JobRepository(factory), lock_ttl_seconds=30)
    transcript_service = TranscriptService(repository=TranscriptRepository(factory))
    asr_service = AsrService(
        repository=AsrRepository(factory),
        transcript_service=transcript_service,
        job_service=job_service,
        provider=provider,
    )
    job_service.register_handler(AsrJobHandler(asr_service=asr_service))
    return asr_service, job_service, transcript_service


def test_asr_job_submits_then_completes_transcript() -> None:
    asr_service, job_service, transcript_service = _build_services()

    data = asr_service.create_recognition(
        object_key="conversation/u/audio.m4a",
        audio_url="https://example.com/audio.m4a",
        language="en-US",
    )

    running = job_service.run_job(job_id=data.job.job_id, worker_id="test-worker")
    assert running.status == int(JobStatus.RUNNING)

    completed = job_service.run_job(job_id=data.job.job_id, worker_id="test-worker")
    assert completed.status == int(JobStatus.COMPLETED)

    recognition = asr_service.get_recognition(recognition_id=data.recognition.recognition_id)
    assert recognition.status == int(AsrRecognitionStatus.COMPLETED)

    transcript = transcript_service.get_transcript(transcript_id=data.transcript.transcript_id)
    assert transcript.status == int(TranscriptStatus.COMPLETED)
    assert len(transcript.utterances) > 0


def test_asr_job_marks_recognition_and_transcript_failed() -> None:
    asr_service, job_service, transcript_service = _build_services_with_provider(FailingAsrProvider())

    data = asr_service.create_recognition(
        object_key="conversation/u/audio.m4a",
        audio_url="https://example.com/audio.m4a",
        language="en-US",
    )

    running = job_service.run_job(job_id=data.job.job_id, worker_id="test-worker")
    assert running.status == int(JobStatus.RUNNING)

    failed = job_service.run_job(job_id=data.job.job_id, worker_id="test-worker")
    assert failed.status == int(JobStatus.FAILED)
    assert failed.error_code == "FIXTURE_FAILED"

    recognition = asr_service.get_recognition(recognition_id=data.recognition.recognition_id)
    assert recognition.status == int(AsrRecognitionStatus.FAILED)
    assert recognition.error_code == "FIXTURE_FAILED"

    transcript = transcript_service.get_transcript(transcript_id=data.transcript.transcript_id)
    assert transcript.status == int(TranscriptStatus.FAILED)
    assert transcript.error_code == "FIXTURE_FAILED"
