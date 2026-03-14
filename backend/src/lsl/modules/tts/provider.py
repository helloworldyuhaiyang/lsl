from __future__ import annotations

from lsl.core.config import Settings
from lsl.modules.tts.providers import FakeTtsProvider, VolcTtsProvider
from lsl.modules.tts.types import TtsProvider, TtsSpeaker, TtsSynthesizeRequest, TtsSynthesizeResult


class NoopTtsProvider:
    provider_name = "noop"

    def get_speakers(self) -> list[TtsSpeaker]:
        return []

    def synthesize(self, req: TtsSynthesizeRequest) -> TtsSynthesizeResult:
        raise NotImplementedError("TTS provider is not implemented")


def create_tts_provider(settings: Settings) -> TtsProvider:
    provider = (settings.TTS_PROVIDER or "fake").strip().lower()
    if provider == "fake":
        return FakeTtsProvider()
    if provider == "volc":
        return VolcTtsProvider(settings)
    if provider == "noop":
        return NoopTtsProvider()
    raise ValueError(f"Unsupported TTS_PROVIDER: {provider}")
