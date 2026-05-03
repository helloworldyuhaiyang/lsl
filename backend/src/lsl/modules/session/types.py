from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SessionListFilters:
    limit: int = 20
    offset: int = 0
    query: str | None = None
    status: int | None = None


@dataclass(frozen=True, slots=True)
class SessionLinks:
    asset_object_key: str | None = None
    current_transcript_id: str | None = None
