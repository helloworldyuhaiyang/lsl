from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ScriptGenerateRequest:
    title: str
    description: str | None
    language: str | None
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
class GeneratedScript:
    utterances: list[GeneratedScriptTurn]


class ScriptGenerator(Protocol):
    provider_name: str

    def generate(self, req: ScriptGenerateRequest) -> GeneratedScript:
        ...
