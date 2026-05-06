from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from collections.abc import Iterator
from typing import Protocol


class ScriptGenerationStatus(IntEnum):
    PENDING = 0
    GENERATING = 1
    COMPLETED = 2
    FAILED = 3


def script_generation_status_to_name(status: int) -> str:
    mapping = {
        int(ScriptGenerationStatus.PENDING): "pending",
        int(ScriptGenerationStatus.GENERATING): "generating",
        int(ScriptGenerationStatus.COMPLETED): "completed",
        int(ScriptGenerationStatus.FAILED): "failed",
    }
    return mapping.get(int(status), "pending")


@dataclass(frozen=True, slots=True)
class ScriptGenerateRequest:
    title: str
    description: str | None
    target_language: str | None
    cue_language: str | None
    prompt: str
    turn_count: int
    speaker_count: int
    difficulty: str | None = None
    cue_style: str | None = None
    must_include: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class GeneratedScriptTurn:
    speaker: str
    cue: str
    text: str


@dataclass(frozen=True, slots=True)
class ScriptSection:
    section_index: int
    title: str
    summary: str
    target_turn_count: int


@dataclass(frozen=True, slots=True)
class GeneratedScript:
    utterances: list[GeneratedScriptTurn]


class ScriptGenerator(Protocol):
    provider_name: str

    def generate(self, req: ScriptGenerateRequest) -> GeneratedScript:
        ...

    def generate_progressively(self, req: ScriptGenerateRequest) -> Iterator[GeneratedScriptTurn]:
        ...

    def plan_sections(self, req: ScriptGenerateRequest) -> list[ScriptSection]:
        ...

    def generate_from_plan_progressively(
        self,
        req: ScriptGenerateRequest,
        sections: list[ScriptSection],
    ) -> Iterator[GeneratedScriptTurn]:
        ...
