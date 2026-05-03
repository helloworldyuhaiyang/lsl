from __future__ import annotations

from lsl.core.config import Settings
from lsl.modules.asr.providers import FakeAsrProvider, VolcAsrProvider
from lsl.modules.asr.types import AsrProvider, NoopAsrProvider


def create_asr_provider(settings: Settings) -> AsrProvider:
    provider = (settings.ASR_PROVIDER or "noop").strip().lower()
    if provider == "fake":
        return FakeAsrProvider()
    if provider == "volc":
        return VolcAsrProvider(settings)
    if provider == "noop":
        return NoopAsrProvider()
    raise ValueError(f"Unsupported ASR_PROVIDER: {provider}")
