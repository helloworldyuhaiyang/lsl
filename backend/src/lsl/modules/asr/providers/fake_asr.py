from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lsl.modules.asr.types import (
    AsrJobRef,
    AsrJobStatus,
    AsrQueryResult,
    AsrSubmitRequest,
    AsrUtterance,
)


class FakeAsrProvider:
    provider_name = "fake"

    def __init__(self, fixture_path: str | None = None) -> None:
        base_dir = Path(__file__).resolve().parent.parent
        path = Path(fixture_path) if fixture_path else (base_dir / "result.json")
        self._fixture = self._load_fixture(path)

    @staticmethod
    def _load_fixture(path: Path) -> dict[str, Any]:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def submit(self, req: AsrSubmitRequest) -> AsrJobRef:
        return AsrJobRef(
            recognition_id=req.recognition_id,
            provider=self.provider_name,
            provider_request_id=req.recognition_id,
            provider_resource_id="fake.bigasr.auc",
            x_tt_logid=f"fake-{req.recognition_id}",
        )

    def query(self, ref: AsrJobRef) -> AsrQueryResult:
        raw_result = self._fixture
        return AsrQueryResult(
            status=AsrJobStatus.SUCCEEDED,
            provider_status_code="20000000",
            provider_message="OK",
            duration_ms=self._extract_duration_ms(raw_result),
            full_text=self._extract_full_text(raw_result),
            utterances=self._extract_utterances(raw_result),
            raw_result=raw_result,
            x_tt_logid=ref.x_tt_logid or f"fake-{ref.provider_request_id}",
        )

    @staticmethod
    def _extract_duration_ms(payload: dict[str, Any]) -> int | None:
        audio_info = payload.get("audio_info", {})
        duration = audio_info.get("duration")
        if isinstance(duration, int):
            return duration

        additions = payload.get("result", {}).get("additions", {})
        fallback = additions.get("duration")
        if isinstance(fallback, str) and fallback.isdigit():
            return int(fallback)
        if isinstance(fallback, int):
            return fallback
        return None

    @staticmethod
    def _extract_full_text(payload: dict[str, Any]) -> str | None:
        text = payload.get("result", {}).get("text")
        return text if isinstance(text, str) else None

    @staticmethod
    def _extract_utterances(payload: dict[str, Any]) -> list[AsrUtterance]:
        items = payload.get("result", {}).get("utterances", [])
        result: list[AsrUtterance] = []

        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                continue

            text = item.get("text")
            start_time = item.get("start_time")
            end_time = item.get("end_time")
            additions = item.get("additions") or {}

            if not isinstance(text, str) or not text.strip():
                continue
            if not isinstance(start_time, int) or not isinstance(end_time, int):
                continue

            speaker = None
            clean_additions: dict[str, object] = {}
            if isinstance(additions, dict):
                speaker_value = additions.get("speaker")
                if isinstance(speaker_value, str):
                    speaker = speaker_value
                clean_additions = {
                    "emotion": additions.get("emotion"),
                    "emotion_degree": additions.get("emotion_degree"),
                    "emotion_score": additions.get("emotion_score"),
                    "emotion_degree_score": additions.get("emotion_degree_score"),
                    "gender": additions.get("gender"),
                    "gender_score": additions.get("gender_score"),
                }
                clean_additions = {key: value for key, value in clean_additions.items() if value is not None}

            result.append(
                AsrUtterance(
                    seq=idx,
                    text=text,
                    speaker=speaker,
                    start_time=start_time,
                    end_time=end_time,
                    additions=clean_additions,
                )
            )
        return result
