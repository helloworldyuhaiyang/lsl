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
from lsl.modules.revision.service import RevisionJobHandler, RevisionService
from lsl.modules.revision.types import RevisionGenerateRequest, RevisionGenerator, RevisionSuggestion
from lsl.modules.session.repo import SessionRepository
from lsl.modules.session.schema import CreateSessionRequest
from lsl.modules.session.service import SessionService
from lsl.modules.transcript.repo import TranscriptRepository
from lsl.modules.transcript.service import TranscriptService
from lsl.modules.transcript.types import TranscriptUtterance


class FakeRevisionGenerator:
    provider_name = "fake-revision"

    def generate(self, req: RevisionGenerateRequest) -> list[RevisionSuggestion]:
        return [
            RevisionSuggestion(
                source_seqs=[0],
                suggested_text="Hello there.",
                score=95,
                issue_tags="style",
                explanations="Made it more natural.",
            ),
            RevisionSuggestion(
                source_seqs=[1],
                suggested_text="Nice to meet you.",
                score=95,
                issue_tags="style",
                explanations="Made it more natural.",
            ),
        ]

    def generate_progressively(self, req: RevisionGenerateRequest) -> Iterator[list[RevisionSuggestion]]:
        for suggestion in self.generate(req):
            yield [suggestion]


def _build_services() -> tuple[RevisionService, JobService, SessionService, TranscriptService]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, class_=OrmSession)
    settings = Settings(STORAGE_PROVIDER="fake", ASSET_BASE_URL="http://assets.test")
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
        generator=FakeRevisionGenerator(),
        session_service=session_service,
        transcript_service=transcript_service,
        job_service=job_service,
    )
    job_service.register_handler(RevisionJobHandler(revision_service=revision_service))
    return revision_service, job_service, session_service, transcript_service


def test_revision_generation_job_updates_revision_items() -> None:
    revision_service, job_service, session_service, transcript_service = _build_services()
    transcript = transcript_service.create_completed_transcript(
        source_type="manual",
        source_entity_id=None,
        language="en-US",
        utterances=[
            TranscriptUtterance(seq=0, speaker="A", text="hello there", start_time=0, end_time=1000),
            TranscriptUtterance(seq=1, speaker="B", text="nice meet you", start_time=1000, end_time=2000),
        ],
    )
    session = session_service.create_session(
        CreateSessionRequest(
            title="Revision fixture",
            f_type=2,
            current_transcript_id=transcript.transcript_id,
        )
    )

    created = revision_service.create_revision(
        session_id=session.session.session_id,
        user_prompt="make it natural",
        force=True,
    )
    assert created.status_name == "generating"
    assert created.job_id is not None
    assert created.items == []

    completed = job_service.run_job(job_id=created.job_id, worker_id="test-worker")
    assert completed.status == int(JobStatus.COMPLETED)

    revision = revision_service.get_revision(session_id=session.session.session_id)
    assert revision.status_name == "completed"
    assert [item.suggested_text for item in revision.items] == ["Hello there.", "Nice to meet you."]
