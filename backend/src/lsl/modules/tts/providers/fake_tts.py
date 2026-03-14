from __future__ import annotations

import io
import wave
from pathlib import Path

from lsl.modules.tts.types import TtsSpeaker, TtsSynthesizeRequest, TtsSynthesizeResult


class FakeTtsProvider:
    provider_name = "fake"

    def __init__(self) -> None:
        self._sample_path = Path(__file__).resolve().parent.parent / "tts_test.mp3"

    def get_speakers(self) -> list[TtsSpeaker]:
        return [
            TtsSpeaker(
                speaker_id="fake_neutral_mp3",
                name="Fake Neutral",
                language="multi",
                gender="unknown",
                style="neutral",
                description="Use bundled demo mp3 for local debugging.",
            )
        ]

    def synthesize(self, req: TtsSynthesizeRequest) -> TtsSynthesizeResult:
        if req.format == "wav":
            return TtsSynthesizeResult(
                audio_bytes=self._build_wav_sample(),
                content_type="audio/wav",
                duration_ms=1000,
                provider_speaker_id=req.provider_speaker_id,
            )

        if req.format != "mp3":
            raise RuntimeError(f"Fake TTS provider does not support format: {req.format}")
        if not self._sample_path.exists():
            raise RuntimeError("tts_test.mp3 is missing for FakeTtsProvider")
        return TtsSynthesizeResult(
            audio_bytes=self._sample_path.read_bytes(),
            content_type="audio/mpeg",
            duration_ms=None,
            provider_speaker_id=req.provider_speaker_id,
        )

    @staticmethod
    def _build_wav_sample() -> bytes:
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(16000)
            wav_file.writeframes(b"\x00\x00" * 16000)
        return buffer.getvalue()
