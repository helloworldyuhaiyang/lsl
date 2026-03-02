from lsl.asr.fake_provider import FakeAsrProvider
from lsl.asr.provider import AsrProvider, NoopAsrProvider
from lsl.config import Settings


def create_asr_provider(settings: Settings) -> AsrProvider:
    provider = (settings.ASR_PROVIDER or "noop").strip().lower()
    if provider == "fake":
        return FakeAsrProvider()
    if provider == "noop":
        return NoopAsrProvider()
    raise ValueError(f"Unsupported ASR_PROVIDER: {provider}")
