from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session as OrmSession
from sqlalchemy.orm import sessionmaker

from lsl.core.db import Base
from lsl.modules.job.repo import JobRepository
from lsl.modules.job.service import JobService
from lsl.modules.job.types import JobStatus
from lsl.modules.revision.repo import RevisionRepository
from lsl.modules.translation.provider import FakeTranslationGenerator
from lsl.modules.translation.repo import TranslationRepository
from lsl.modules.translation.service import TranslationJobHandler, TranslationService
from lsl.modules.transcript.repo import TranscriptRepository
from lsl.modules.transcript.service import TranscriptService
from lsl.modules.transcript.types import TranscriptUtterance


def _build_services() -> tuple[TranslationService, JobService, TranscriptService]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, class_=OrmSession)

    job_service = JobService(repository=JobRepository(factory), lock_ttl_seconds=30)
    transcript_service = TranscriptService(repository=TranscriptRepository(factory))
    translation_service = TranslationService(
        repository=TranslationRepository(factory),
        generator=FakeTranslationGenerator(),
        transcript_service=transcript_service,
        revision_repository=RevisionRepository(factory),
        job_service=job_service,
    )
    job_service.register_handler(TranslationJobHandler(translation_service=translation_service))
    return translation_service, job_service, transcript_service


def test_translation_generation_job_updates_items() -> None:
    translation_service, job_service, transcript_service = _build_services()
    transcript = transcript_service.create_completed_transcript(
        source_type="manual",
        source_entity_id=None,
        language="en-US",
        utterances=[
            TranscriptUtterance(seq=0, speaker="A", text="hello there", start_time=0, end_time=1000),
            TranscriptUtterance(seq=1, speaker="B", text="nice to meet you", start_time=1000, end_time=2000),
        ],
    )

    created = translation_service.create_translation(
        source_type="transcript",
        source_entity_id=transcript.transcript_id,
        target_language="zh-CN",
    )
    assert created.status_name == "generating"
    assert created.job_id is not None
    assert [item.status_name for item in created.items] == ["pending", "pending"]

    completed = job_service.run_job(job_id=created.job_id, worker_id="test-worker")
    assert completed.status == int(JobStatus.COMPLETED)

    translation = translation_service.get_translation(
        source_type="transcript",
        source_entity_id=transcript.transcript_id,
        target_language="zh-CN",
    )
    assert translation.status_name == "completed"
    assert [item.translated_text for item in translation.items] == [
        "译文：hello there",
        "译文：nice to meet you",
    ]


def test_translation_retry_recovers_generating_items() -> None:
    translation_service, job_service, transcript_service = _build_services()
    transcript = transcript_service.create_completed_transcript(
        source_type="manual",
        source_entity_id=None,
        language="en-US",
        utterances=[
            TranscriptUtterance(seq=0, speaker="A", text="hello there", start_time=0, end_time=1000),
        ],
    )

    created = translation_service.create_translation(
        source_type="transcript",
        source_entity_id=transcript.transcript_id,
        target_language="zh-CN",
    )
    translation_service._repository.mark_items_generating(
        translation_id=created.translation_id,
        source_item_keys=[created.items[0].source_item_key],
    )

    retried = translation_service.create_translation(
        source_type="transcript",
        source_entity_id=transcript.transcript_id,
        target_language="zh-CN",
        force=True,
    )
    assert retried.job_id is not None

    completed = job_service.run_job(job_id=retried.job_id, worker_id="test-worker")
    assert completed.status == int(JobStatus.COMPLETED)

    translation = translation_service.get_translation(
        source_type="transcript",
        source_entity_id=transcript.transcript_id,
        target_language="zh-CN",
    )
    assert translation.status_name == "completed"
    assert translation.items[0].status_name == "completed"
    assert translation.items[0].translated_text == "译文：hello there"
