from __future__ import annotations

from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session as OrmSession
from sqlalchemy.orm import sessionmaker

from lsl.core.config import Settings
from lsl.core.db import Base
from lsl.modules.asset.providers import FakeStorageProvider
from lsl.modules.asset.repo import AssetRepository
from lsl.modules.asset.service import AssetService
from lsl.modules.job.repo import JobRepository
from lsl.modules.job.service import JobService
from lsl.modules.job.types import JobStatus
from lsl.modules.revision.repo import RevisionRepository
from lsl.modules.revision.service import RevisionService
from lsl.modules.revision.types import GeneratedRevisionItem, RevisionGenerateRequest, RevisionSuggestion
from lsl.modules.session.repo import SessionRepository
from lsl.modules.session.schema import CreateSessionRequest
from lsl.modules.session.service import SessionService
from lsl.modules.transcript.repo import TranscriptRepository
from lsl.modules.transcript.service import TranscriptService
from lsl.modules.transcript.types import TranscriptUtterance
from lsl.modules.tts.cache import TtsCache
from lsl.modules.tts.providers.fake_tts import FakeTtsProvider
from lsl.modules.tts.repo import TtsRepository
from lsl.modules.tts.service import TtsJobHandler, TtsService
from lsl.modules.tts.types import TtsSynthesisStatus


class NoopRevisionGenerator:
    provider_name = "noop"

    def generate(self, req: RevisionGenerateRequest) -> list[RevisionSuggestion]:
        return []

    def generate_progressively(self, req: RevisionGenerateRequest) -> Iterator[list[RevisionSuggestion]]:
        return iter(())


def _build_services() -> tuple[TtsService, JobService, SessionService, RevisionService, TranscriptService]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, class_=OrmSession)
    settings = Settings(
        STORAGE_PROVIDER="fake",
        ASSET_BASE_URL="http://assets.test",
        TTS_DEFAULT_FORMAT="wav",
        TTS_REDIS_URL="redis://127.0.0.1:1/0",
    )
    asset_service = AssetService(
        settings=settings,
        storage=FakeStorageProvider(),
        repository=AssetRepository(factory),
    )
    job_service = JobService(repository=JobRepository(factory), lock_ttl_seconds=30)
    transcript_service = TranscriptService(repository=TranscriptRepository(factory))
    session_service = SessionService(
        repository=SessionRepository(factory),
        asset_service=asset_service,
        transcript_service=transcript_service,
    )
    revision_service = RevisionService(
        repository=RevisionRepository(factory),
        generator=NoopRevisionGenerator(),
        session_service=session_service,
        transcript_service=transcript_service,
    )
    tts_service = TtsService(
        repository=TtsRepository(factory),
        provider=FakeTtsProvider(),
        cache=TtsCache(redis_url=settings.TTS_REDIS_URL, ttl_seconds=settings.TTS_CACHE_TTL_SECONDS),
        session_service=session_service,
        revision_service=revision_service,
        asset_service=asset_service,
        job_service=job_service,
        settings=settings,
    )
    job_service.register_handler(TtsJobHandler(tts_service=tts_service))
    return tts_service, job_service, session_service, revision_service, transcript_service


def test_tts_synthesis_job_generates_full_audio_asset() -> None:
    tts_service, job_service, session_service, revision_service, transcript_service = _build_services()
    transcript = transcript_service.create_completed_transcript(
        source_type="manual",
        source_entity_id=None,
        language="en-US",
        utterances=[
            TranscriptUtterance(seq=0, speaker="A", text="Hello there.", start_time=0, end_time=1000),
            TranscriptUtterance(seq=1, speaker="B", text="Nice to meet you.", start_time=1000, end_time=2000),
        ],
    )
    session = session_service.create_session(
        CreateSessionRequest(
            title="TTS fixture",
            f_type=2,
            current_transcript_id=transcript.transcript_id,
        )
    )
    revision_service.create_generated_revision(
        session_id=session.session.session_id,
        transcript_id=transcript.transcript_id,
        user_prompt=None,
        items=[
            GeneratedRevisionItem(
                transcript_id=transcript.transcript_id,
                source_seq_start=0,
                source_seq_end=0,
                source_seq_count=1,
                source_seqs=[0],
                speaker="A",
                start_time=0,
                end_time=1000,
                original_text="Hello there.",
                suggested_text="Hello there.",
            ),
            GeneratedRevisionItem(
                transcript_id=transcript.transcript_id,
                source_seq_start=1,
                source_seq_end=1,
                source_seq_count=1,
                source_seqs=[1],
                speaker="B",
                start_time=1000,
                end_time=2000,
                original_text="Nice to meet you.",
                suggested_text="Nice to meet you.",
            ),
        ],
    )

    created = tts_service.create_synthesis(session_id=session.session.session_id, force=True)
    assert created.job is not None

    completed = job_service.run_job(job_id=created.job.job_id, worker_id="test-worker")
    assert completed.status == int(JobStatus.COMPLETED)

    synthesis = tts_service.get_synthesis(session_id=session.session.session_id)
    assert synthesis.status == int(TtsSynthesisStatus.COMPLETED)
    assert synthesis.full_asset_url is not None
    assert synthesis.item_count == 2
    assert synthesis.completed_item_count == 2
    assert synthesis.full_duration_ms == 2000
