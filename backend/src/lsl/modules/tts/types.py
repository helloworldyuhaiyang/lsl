from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Protocol


class TtsSynthesisStatus(IntEnum):
    PENDING = 0
    GENERATING = 1
    COMPLETED = 2
    PARTIAL = 3
    FAILED = 4


def status_code_to_name(status_code: int) -> str:
    mapping = {
        int(TtsSynthesisStatus.PENDING): "pending",
        int(TtsSynthesisStatus.GENERATING): "generating",
        int(TtsSynthesisStatus.COMPLETED): "completed",
        int(TtsSynthesisStatus.PARTIAL): "partial",
        int(TtsSynthesisStatus.FAILED): "failed",
    }
    return mapping.get(int(status_code), "pending")


@dataclass(frozen=True, slots=True)
class TtsSpeaker:
    speaker_id: str
    name: str
    language: str | None = None
    gender: str | None = None
    style: str | None = None
    description: str | None = None


@dataclass(frozen=True, slots=True)
class TtsSpeakerMapping:
    conversation_speaker: str
    provider_speaker_id: str


@dataclass(frozen=True, slots=True)
class TtsSettingsValue:
    session_id: str
    format: str
    emotion_scale: float
    speech_rate: float
    loudness_rate: float
    speaker_mappings: list[TtsSpeakerMapping] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ParsedTtsContent:
    content: str
    plain_text: str
    cue_texts: list[str]


@dataclass(frozen=True, slots=True)
class CachedAudio:
    audio_bytes: bytes
    content_type: str
    duration_ms: int | None
    provider_speaker_id: str
    content_hash: str


@dataclass(frozen=True, slots=True)
class TtsSynthesizeRequest:
    session_id: str
    content: str
    plain_text: str
    cue_texts: list[str]
    provider_speaker_id: str
    format: str
    emotion_scale: float
    speech_rate: float
    loudness_rate: float


@dataclass(frozen=True, slots=True)
class TtsSynthesizeResult:
    audio_bytes: bytes
    content_type: str
    duration_ms: int | None
    provider_speaker_id: str


@dataclass(slots=True)
class StoredSynthesisItem:
    source_item_id: str
    source_seq_start: int
    source_seq_end: int
    source_seqs: list[int]
    conversation_speaker: str | None
    provider_speaker_id: str
    content: str
    plain_text: str
    cue_texts: list[str]
    content_hash: str
    duration_ms: int | None = None
    status: int = int(TtsSynthesisStatus.PENDING)
    error_code: str | None = None
    error_message: str | None = None


class TtsProvider(Protocol):
    provider_name: str

    def get_speakers(self) -> list[TtsSpeaker]:
        ...

    def synthesize(self, req: TtsSynthesizeRequest) -> TtsSynthesizeResult:
        ...
