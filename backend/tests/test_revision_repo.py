from __future__ import annotations

import pytest

from lsl.modules.revision.repo import RevisionRepository
from lsl.modules.revision.types import GeneratedRevisionItem


def _build_item(*, source_seqs: list[int]) -> GeneratedRevisionItem:
    return GeneratedRevisionItem(
        transcript_id="00000000-0000-0000-0000-000000000001",
        source_seq_start=source_seqs[0],
        source_seq_end=source_seqs[-1],
        source_seq_count=len(source_seqs),
        source_seqs=source_seqs,
        speaker="student",
        start_time=0,
        end_time=1000,
        original_text="i go there",
        suggested_text="I go there.",
        draft_text="[自然的 / 平稳的 / 日常对话] I go there.",
        score=80,
        issue_tags="调试文案",
        explanations="调试说明",
    )


def test_save_revision_rejects_overlapping_source_seqs() -> None:
    repository = RevisionRepository(session_factory=None)  # type: ignore[arg-type]

    with pytest.raises(RuntimeError, match=r"Overlapping source_seqs in revision items: 1"):
        repository.save_revision(
            session_id="00000000-0000-0000-0000-000000000010",
            transcript_id="00000000-0000-0000-0000-000000000020",
            user_prompt=None,
            status=2,
            items=[
                _build_item(source_seqs=[0, 1]),
                _build_item(source_seqs=[1, 2]),
            ],
        )
