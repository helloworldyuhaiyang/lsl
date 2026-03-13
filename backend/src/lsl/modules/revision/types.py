from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Iterator, Protocol


class RevisionStatus(IntEnum):
    PENDING = 0
    GENERATING = 1
    COMPLETED = 2
    FAILED = 3


def status_code_to_name(status: int) -> str:
    mapping = {
        int(RevisionStatus.PENDING): "pending",
        int(RevisionStatus.GENERATING): "generating",
        int(RevisionStatus.COMPLETED): "completed",
        int(RevisionStatus.FAILED): "failed",
    }
    return mapping.get(int(status), "pending")


@dataclass(slots=True)
class GeneratedRevisionItem:
    task_id: str
    source_seq_start: int
    source_seq_end: int
    source_seq_count: int
    source_seqs: list[int]
    speaker: str | None
    start_time: int
    end_time: int
    original_text: str
    suggested_text: str
    suggested_cue: str | None
    draft_text: str | None = None
    draft_cue: str | None = None
    score: int = 0
    issue_tags: str = ""
    explanations: str = ""


@dataclass(frozen=True, slots=True)
class RevisionPromptUtterance:
    utterance_seq: int
    speaker: str | None
    text: str
    addions: dict[str, str | int | float] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RevisionGenerateRequest:
    task_id: str
    user_prompt: str | None
    utterances: list[RevisionPromptUtterance]


@dataclass(frozen=True, slots=True)
class RevisionSegment:
    segment_index: int
    start_seq: int
    end_seq: int
    title: str = ""
    summary: str = ""


class RevisionGenerator(Protocol):
    provider_name: str

    def generate(self, req: RevisionGenerateRequest) -> list["RevisionSuggestion"]:
        ...

    def generate_progressively(self, req: RevisionGenerateRequest) -> Iterator[list["RevisionSuggestion"]]:
        ...


@dataclass(slots=True)
class RevisionSuggestion:
    source_seqs: list[int]
    suggested_text: str
    suggested_cue: str | None
    score: int
    issue_tags: str = ""
    explanations: str = ""
