from __future__ import annotations

import pytest

from lsl.modules.revision.repo import RevisionRepository
from lsl.modules.revision.types import GeneratedRevisionItem


def _build_item(seq: int) -> GeneratedRevisionItem:
    return GeneratedRevisionItem(
        task_id="00000000-0000-0000-0000-000000000001",
        utterance_seq=seq,
        speaker="student",
        start_time=0,
        end_time=1000,
        original_text="i go there",
        suggested_text="I go there.",
        suggested_cue="[自然的 / 平稳的 / 日常对话]",
        score=80,
        issue_tags="调试文案",
        explanations="调试说明",
    )


def test_save_revision_rejects_duplicate_utterance_seq() -> None:
    repository = RevisionRepository(session_factory=None)  # type: ignore[arg-type]

    with pytest.raises(RuntimeError, match=r"Duplicate utterance_seq in revision items: 0"):
        repository.save_revision(
            session_id="00000000-0000-0000-0000-000000000010",
            task_id="00000000-0000-0000-0000-000000000020",
            user_prompt=None,
            status=2,
            items=[_build_item(0), _build_item(0)],
        )
