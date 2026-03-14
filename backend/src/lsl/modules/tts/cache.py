from __future__ import annotations

import logging
import pickle
import time
from dataclasses import dataclass

from lsl.modules.tts.types import CachedAudio

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class _MemoryCacheItem:
    expires_at: float
    value: CachedAudio


class TtsCache:
    def __init__(self, *, redis_url: str, ttl_seconds: int) -> None:
        self._ttl_seconds = ttl_seconds
        self._memory: dict[str, _MemoryCacheItem] = {}
        self._redis = None

        try:
            from redis import Redis

            self._redis = Redis.from_url(redis_url, decode_responses=False)
            self._redis.ping()
        except Exception as exc:  # pragma: no cover
            logger.warning("TTS redis cache unavailable, falling back to in-memory cache: %s", exc)
            self._redis = None

    def get_audio(self, cache_key: str) -> CachedAudio | None:
        if self._redis is not None:
            try:
                payload = self._redis.get(cache_key)
                if not payload:
                    return None
                return pickle.loads(payload)
            except Exception as exc:  # pragma: no cover
                logger.warning("Failed to read TTS cache key=%s: %s", cache_key, exc)

        item = self._memory.get(cache_key)
        if item is None:
            return None
        if item.expires_at <= time.time():
            self._memory.pop(cache_key, None)
            return None
        return item.value

    def set_audio(self, cache_key: str, audio: CachedAudio) -> None:
        if self._redis is not None:
            try:
                self._redis.setex(cache_key, self._ttl_seconds, pickle.dumps(audio))
                return
            except Exception as exc:  # pragma: no cover
                logger.warning("Failed to write TTS cache key=%s: %s", cache_key, exc)

        self._memory[cache_key] = _MemoryCacheItem(
            expires_at=time.time() + self._ttl_seconds,
            value=audio,
        )
