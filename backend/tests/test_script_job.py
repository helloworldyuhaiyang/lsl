from __future__ import annotations

from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session as OrmSession
from sqlalchemy.orm import sessionmaker

from lsl.core.config import Settings
from lsl.core.db import Base
from lsl.modules.asset.providers import FakeStorageProvider
from lsl.modules.asset.service import AssetService
from lsl.modules.job.repo import JobRepository
from lsl.modules.job.service import JobService
from lsl.modules.job.types import JobStatus
from lsl.modules.revision.repo import RevisionRepository
from lsl.modules.revision.service import RevisionService
from lsl.modules.revision.types import RevisionGenerateRequest, RevisionGenerator, RevisionSuggestion
from lsl.modules.script.repo import ScriptRepository
from lsl.modules.script.schema import GenerateScriptSessionRequest
from lsl.modules.script.service import ScriptJobHandler, ScriptService
from lsl.modules.script.types import GeneratedScript, GeneratedScriptTurn, ScriptGenerateRequest, ScriptGenerator
from lsl.modules.session.repo import SessionRepository
from lsl.modules.session.service import SessionService
from lsl.modules.transcript.repo import TranscriptRepository
from lsl.modules.transcript.service import TranscriptService


class FakeScriptGenerator:
    provider_name = "fake-script"

    def generate(self, req: ScriptGenerateRequest) -> GeneratedScript:
        return GeneratedScript(
            utterances=[
                GeneratedScriptTurn(speaker="A", cue="calm", text="Hello there."),
                GeneratedScriptTurn(speaker="B", cue="friendly", text="Nice to meet you."),
            ]
        )

    def generate_progressively(self, req: ScriptGenerateRequest) -> Iterator[GeneratedScriptTurn]:
        yield from self.generate(req).utterances


class NoopRevisionGenerator:
    provider_name = "noop"

    def generate(self, req: RevisionGenerateRequest) -> list[RevisionSuggestion]:
        return []

    def generate_progressively(self, req: RevisionGenerateRequest) -> Iterator[list[RevisionSuggestion]]:
        return iter(())


def _build_services() -> tuple[ScriptService, JobService, TranscriptService, RevisionService]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, class_=OrmSession)
    settings = Settings(STORAGE_PROVIDER="fake", ASSET_BASE_URL="http://assets.test")
    asset_service = AssetService(settings=settings, storage=FakeStorageProvider(), repository=None)
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
    script_service = ScriptService(
        repository=ScriptRepository(factory),
        generator=FakeScriptGenerator(),
        session_service=session_service,
        transcript_service=transcript_service,
        revision_service=revision_service,
        job_service=job_service,
    )
    job_service.register_handler(ScriptJobHandler(script_service=script_service))
    return script_service, job_service, transcript_service, revision_service


def test_script_generation_job_creates_transcript_and_revision() -> None:
    script_service, job_service, transcript_service, revision_service = _build_services()

    data = script_service.generate_session(
        GenerateScriptSessionRequest(
            title="Interview",
            prompt="practice an interview",
        )
    )

    completed = job_service.run_job(job_id=data.job.job_id, worker_id="test-worker")
    assert completed.status == int(JobStatus.COMPLETED)

    generation = script_service.get_generation(generation_id=data.generation.generation_id)
    assert generation.transcript_id is not None
    preview = script_service.get_generation_preview(generation_id=data.generation.generation_id)
    assert [item.text for item in preview.items] == ["Hello there.", "Nice to meet you."]

    transcript = transcript_service.get_transcript(transcript_id=generation.transcript_id)
    assert [item.text for item in transcript.utterances] == ["Hello there.", "Nice to meet you."]

    revision = revision_service.get_revision(session_id=data.session.session.session_id)
    assert revision.transcript_id == generation.transcript_id
    assert len(revision.items) == 2
