from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session as OrmSession
from sqlalchemy.orm import sessionmaker

from lsl.core.db import Base
from lsl.modules.transcript.repo import TranscriptRepository
from lsl.modules.transcript.service import TranscriptService
from lsl.modules.transcript.types import TranscriptStatus, TranscriptUtterance


def _build_service() -> TranscriptService:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, class_=OrmSession)
    return TranscriptService(repository=TranscriptRepository(factory))


def test_transcript_service_creates_completed_transcript() -> None:
    service = _build_service()

    transcript = service.create_completed_transcript(
        source_type="manual",
        source_entity_id="debug-1",
        language="en-US",
        utterances=[
            TranscriptUtterance(seq=0, text=" hello   world ", speaker="A", start_time=0, end_time=1200),
            TranscriptUtterance(seq=1, text="second line", speaker="B", start_time=1200, end_time=2600),
        ],
        raw_result={"source": "test"},
    )

    assert transcript.status == int(TranscriptStatus.COMPLETED)
    assert transcript.duration_ms == 2600
    assert transcript.full_text == "hello world\nsecond line"
    assert [item.text for item in transcript.utterances] == ["hello world", "second line"]

    fetched = service.get_transcript(transcript_id=transcript.transcript_id, include_raw=True)
    assert fetched.raw_result == {"source": "test"}
    assert len(fetched.utterances) == 2


def test_transcript_service_marks_pending_transcript_failed() -> None:
    service = _build_service()

    transcript = service.create_pending_transcript(source_type="asr", source_entity_id=None)
    failed = service.mark_failed(
        transcript_id=transcript.transcript_id,
        error_code="provider_error",
        error_message="failed",
    )

    assert failed.status == int(TranscriptStatus.FAILED)
    assert failed.error_code == "provider_error"
