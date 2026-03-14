from __future__ import annotations

import hashlib
import io
import json
import logging
import re
import uuid
import wave
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

from lsl.core.config import Settings
from lsl.modules.asset.service import AssetService
from lsl.modules.revision.schema import RevisionData, RevisionItemData
from lsl.modules.revision.service import RevisionService
from lsl.modules.session.service import SessionService
from lsl.modules.tts.cache import TtsCache
from lsl.modules.tts.model import SessionTtsSettingsModel, SpeechSynthesisModel
from lsl.modules.tts.repo import TtsRepository
from lsl.modules.tts.schema import (
    GenerateTtsItemRequest,
    TtsSettingsData,
    TtsSpeakerData,
    TtsSynthesisData,
    TtsSynthesisItemData,
    UpdateTtsSettingsRequest,
)
from lsl.modules.tts.types import (
    CachedAudio,
    ParsedTtsContent,
    StoredSynthesisItem,
    TtsProvider,
    TtsSettingsValue,
    TtsSpeaker,
    TtsSpeakerMapping,
    TtsSynthesisStatus,
    TtsSynthesizeRequest,
)

logger = logging.getLogger(__name__)

_CUE_SEGMENT_PATTERN = re.compile(r"\[[^[\]]*]")
_TTS_BACKGROUND_MAX_WORKERS = 2


class TtsService:
    def __init__(
        self,
        *,
        repository: TtsRepository,
        provider: TtsProvider,
        cache: TtsCache,
        session_service: SessionService,
        revision_service: RevisionService,
        asset_service: AssetService,
        settings: Settings,
    ) -> None:
        self._repository = repository
        self._provider = provider
        self._cache = cache
        self._session_service = session_service
        self._revision_service = revision_service
        self._asset_service = asset_service
        self._settings = settings
        self._background_executor = ThreadPoolExecutor(
            max_workers=_TTS_BACKGROUND_MAX_WORKERS,
            thread_name_prefix="tts-job",
        )
        self._job_tokens: dict[str, str] = {}
        self._job_tokens_lock = Lock()

    def shutdown(self) -> None:
        self._background_executor.shutdown(wait=False, cancel_futures=False)

    def list_speakers(self, *, provider_name: str) -> list[TtsSpeakerData]:
        normalized_provider = (provider_name or "").strip().lower()
        if normalized_provider not in {"active", "current", self._provider.provider_name}:
            raise ValueError("unsupported tts provider")
        speakers = self._provider.get_speakers()
        if not speakers:
            raise RuntimeError("No available TTS speakers. Configure TTS_PROVIDER=fake or volc.")
        return [
            TtsSpeakerData(
                speaker_id=item.speaker_id,
                name=item.name,
                language=item.language,
                gender=item.gender,
                style=item.style,
                description=item.description,
            )
            for item in speakers
        ]

    def get_settings(self, *, session_id: str) -> TtsSettingsData:
        self._session_service.get_session(session_id, auto_refresh=False)
        model = self._repository.get_settings_by_session_id(session_id)
        return self._to_settings_data(self._settings_value_from_model(session_id=session_id, model=model))

    def update_settings(self, *, payload: UpdateTtsSettingsRequest) -> TtsSettingsData:
        self._session_service.get_session(payload.session_id, auto_refresh=False)
        speaker_mappings = self._normalize_speaker_mappings(payload.speaker_mappings)
        self._validate_provider_speakers(speaker_mappings)
        model = self._repository.save_settings(
            session_id=payload.session_id,
            format=payload.format,
            emotion_scale=payload.emotion_scale,
            speech_rate=payload.speech_rate,
            loudness_rate=payload.loudness_rate,
            speaker_mappings_json=[
                {
                    "conversation_speaker": item.conversation_speaker,
                    "provider_speaker_id": item.provider_speaker_id,
                }
                for item in speaker_mappings
            ],
        )
        return self._to_settings_data(self._settings_value_from_model(session_id=payload.session_id, model=model))

    def generate_item_audio(
        self,
        *,
        item_id: str,
        payload: GenerateTtsItemRequest,
    ) -> tuple[bytes, str]:
        revision = self._revision_service.get_revision(session_id=payload.session_id)
        item = self._find_revision_item(revision=revision, item_id=item_id)
        settings_value = self._settings_value_from_model(
            session_id=payload.session_id,
            model=self._repository.get_settings_by_session_id(payload.session_id),
        )
        available_speakers = self._provider.get_speakers()
        provider_speaker_id = self._resolve_provider_speaker_id(
            conversation_speaker=item.speaker,
            settings_value=settings_value,
            speakers=available_speakers,
        )
        parsed = self._parse_content(payload.content)
        content_hash = self._build_content_hash(
            parsed=parsed,
            provider_speaker_id=provider_speaker_id,
            settings_value=settings_value,
        )
        cache_key = self._build_cache_key(provider=self._provider.provider_name, content_hash=content_hash)

        if not payload.force:
            cached = self._cache.get_audio(cache_key)
            if cached is not None:
                return cached.audio_bytes, cached.content_type

        result = self._provider.synthesize(
            TtsSynthesizeRequest(
                session_id=payload.session_id,
                content=payload.content,
                plain_text=parsed.plain_text,
                cue_texts=parsed.cue_texts,
                provider_speaker_id=provider_speaker_id,
                format=settings_value.format,
                emotion_scale=settings_value.emotion_scale,
                speech_rate=settings_value.speech_rate,
                loudness_rate=settings_value.loudness_rate,
            )
        )
        self._cache.set_audio(
            cache_key,
            CachedAudio(
                audio_bytes=result.audio_bytes,
                content_type=result.content_type,
                duration_ms=result.duration_ms,
                provider_speaker_id=provider_speaker_id,
                content_hash=content_hash,
            ),
        )
        return result.audio_bytes, result.content_type

    def get_synthesis(self, *, session_id: str) -> TtsSynthesisData:
        model = self._repository.get_synthesis_by_session_id(session_id)
        if model is None:
            raise ValueError("tts synthesis not found")
        return self._to_synthesis_data(model)

    def create_synthesis(self, *, session_id: str, force: bool = False) -> TtsSynthesisData:
        self._session_service.get_session(session_id, auto_refresh=False)
        revision = self._revision_service.get_revision(session_id=session_id)
        settings_value = self._settings_value_from_model(
            session_id=session_id,
            model=self._repository.get_settings_by_session_id(session_id),
        )
        available_speakers = self._provider.get_speakers()
        items = self._build_synthesis_items(
            revision=revision,
            settings_value=settings_value,
            speakers=available_speakers,
        )
        full_content_hash = self._build_full_content_hash(
            provider=self._provider.provider_name,
            settings_value=settings_value,
            items=items,
        )
        existing = self._repository.get_synthesis_by_session_id(session_id)
        if existing is not None and not force and existing.full_content_hash == full_content_hash:
            if int(existing.status) == int(TtsSynthesisStatus.COMPLETED) and existing.full_asset_object_key:
                return self._to_synthesis_data(existing)
            if int(existing.status) == int(TtsSynthesisStatus.GENERATING):
                return self._to_synthesis_data(existing)

        pending_items = [
            StoredSynthesisItem(
                source_item_id=item.source_item_id,
                source_seq_start=item.source_seq_start,
                source_seq_end=item.source_seq_end,
                source_seqs=item.source_seqs,
                conversation_speaker=item.conversation_speaker,
                provider_speaker_id=item.provider_speaker_id,
                content=item.content,
                plain_text=item.plain_text,
                cue_texts=item.cue_texts,
                content_hash=item.content_hash,
                duration_ms=item.duration_ms,
                status=int(TtsSynthesisStatus.PENDING),
            )
            for item in items
        ]
        model = self._repository.save_synthesis(
            session_id=session_id,
            provider=self._provider.provider_name,
            full_content_hash=full_content_hash,
            status=int(TtsSynthesisStatus.GENERATING),
            items=pending_items,
            full_asset_object_key=None,
            full_duration_ms=None,
            error_code=None,
            error_message=None,
        )

        job_token = self._register_job(session_id)
        try:
            self._background_executor.submit(
                self._run_synthesis_job,
                session_id,
                full_content_hash,
                items,
                settings_value,
                force,
                job_token,
            )
        except Exception as exc:
            self._clear_job(session_id=session_id, job_token=job_token)
            self._repository.save_synthesis(
                session_id=session_id,
                provider=self._provider.provider_name,
                full_content_hash=full_content_hash,
                status=int(TtsSynthesisStatus.FAILED),
                items=pending_items,
                full_asset_object_key=None,
                full_duration_ms=None,
                error_code="tts_job_schedule_failed",
                error_message=str(exc),
            )
            raise RuntimeError(f"Failed to schedule tts job: {exc}") from exc

        return self._to_synthesis_data(model)

    def _run_synthesis_job(
        self,
        session_id: str,
        full_content_hash: str,
        items: list[StoredSynthesisItem],
        settings_value: TtsSettingsValue,
        force: bool,
        job_token: str,
    ) -> None:
        current_items = [
            StoredSynthesisItem(
                source_item_id=item.source_item_id,
                source_seq_start=item.source_seq_start,
                source_seq_end=item.source_seq_end,
                source_seqs=item.source_seqs,
                conversation_speaker=item.conversation_speaker,
                provider_speaker_id=item.provider_speaker_id,
                content=item.content,
                plain_text=item.plain_text,
                cue_texts=list(item.cue_texts),
                content_hash=item.content_hash,
                status=int(TtsSynthesisStatus.PENDING),
            )
            for item in items
        ]
        audio_segments: list[bytes] = []
        durations: list[int | None] = []

        try:
            for index, item in enumerate(items):
                if not self._is_active_job(session_id=session_id, job_token=job_token):
                    logger.info("TTS job superseded session_id=%s", session_id)
                    return

                try:
                    cached = None if force else self._cache.get_audio(self._build_cache_key(self._provider.provider_name, item.content_hash))
                    if cached is None:
                        result = self._provider.synthesize(
                            TtsSynthesizeRequest(
                                session_id=session_id,
                                content=item.content,
                                plain_text=item.plain_text,
                                cue_texts=item.cue_texts,
                                provider_speaker_id=item.provider_speaker_id,
                                format=settings_value.format,
                                emotion_scale=settings_value.emotion_scale,
                                speech_rate=settings_value.speech_rate,
                                loudness_rate=settings_value.loudness_rate,
                            )
                        )
                        cached = CachedAudio(
                            audio_bytes=result.audio_bytes,
                            content_type=result.content_type,
                            duration_ms=result.duration_ms,
                            provider_speaker_id=item.provider_speaker_id,
                            content_hash=item.content_hash,
                        )
                        self._cache.set_audio(
                            self._build_cache_key(self._provider.provider_name, item.content_hash),
                            cached,
                        )

                    audio_segments.append(cached.audio_bytes)
                    durations.append(cached.duration_ms)
                    current_items[index] = self._replace_stored_item(
                        item,
                        duration_ms=cached.duration_ms,
                        status=int(TtsSynthesisStatus.COMPLETED),
                        error_code=None,
                        error_message=None,
                    )
                except Exception as exc:
                    logger.exception("TTS item generation failed session_id=%s item_id=%s", session_id, item.source_item_id)
                    current_items[index] = self._replace_stored_item(
                        item,
                        duration_ms=None,
                        status=int(TtsSynthesisStatus.FAILED),
                        error_code="tts_item_generation_failed",
                        error_message=str(exc),
                    )

                self._repository.save_synthesis(
                    session_id=session_id,
                    provider=self._provider.provider_name,
                    full_content_hash=full_content_hash,
                    status=int(TtsSynthesisStatus.GENERATING),
                    items=current_items,
                    full_asset_object_key=None,
                    full_duration_ms=None,
                    error_code=None,
                    error_message=None,
                )

            completed_count = sum(1 for item in current_items if int(item.status) == int(TtsSynthesisStatus.COMPLETED))
            failed_count = sum(1 for item in current_items if int(item.status) == int(TtsSynthesisStatus.FAILED))

            if failed_count > 0:
                status = int(TtsSynthesisStatus.PARTIAL if completed_count > 0 else TtsSynthesisStatus.FAILED)
                self._repository.save_synthesis(
                    session_id=session_id,
                    provider=self._provider.provider_name,
                    full_content_hash=full_content_hash,
                    status=status,
                    items=current_items,
                    full_asset_object_key=None,
                    full_duration_ms=None,
                    error_code="tts_partial_failed" if completed_count > 0 else "tts_generation_failed",
                    error_message=None if completed_count > 0 else "All TTS items failed",
                )
                return

            full_audio = self._merge_audio_segments(
                format_name=settings_value.format,
                audio_segments=audio_segments,
            )
            asset = self._asset_service.save_generated_asset(
                category="tts",
                entity_id=session_id,
                filename=f"{uuid.uuid4().hex}.{settings_value.format}",
                content_type=self._content_type_for_format(settings_value.format),
                data=full_audio,
            )
            full_duration_ms = self._sum_durations(durations)
            self._repository.save_synthesis(
                session_id=session_id,
                provider=self._provider.provider_name,
                full_content_hash=full_content_hash,
                status=int(TtsSynthesisStatus.COMPLETED),
                items=current_items,
                full_asset_object_key=str(asset["object_key"]),
                full_duration_ms=full_duration_ms,
                error_code=None,
                error_message=None,
            )
        except Exception as exc:
            logger.exception("TTS background job failed session_id=%s", session_id)
            self._repository.save_synthesis(
                session_id=session_id,
                provider=self._provider.provider_name,
                full_content_hash=full_content_hash,
                status=int(TtsSynthesisStatus.FAILED),
                items=current_items,
                full_asset_object_key=None,
                full_duration_ms=None,
                error_code="tts_generation_failed",
                error_message=str(exc),
            )
        finally:
            self._clear_job(session_id=session_id, job_token=job_token)

    def _build_synthesis_items(
        self,
        *,
        revision: RevisionData,
        settings_value: TtsSettingsValue,
        speakers: list[TtsSpeaker],
    ) -> list[StoredSynthesisItem]:
        result: list[StoredSynthesisItem] = []
        for item in sorted(revision.items, key=lambda current: (current.source_seq_start, current.source_seq_end)):
            content = (item.draft_text or item.suggested_text or "").strip()
            parsed = self._parse_content(content)
            provider_speaker_id = self._resolve_provider_speaker_id(
                conversation_speaker=item.speaker,
                settings_value=settings_value,
                speakers=speakers,
            )
            content_hash = self._build_content_hash(
                parsed=parsed,
                provider_speaker_id=provider_speaker_id,
                settings_value=settings_value,
            )
            result.append(
                StoredSynthesisItem(
                    source_item_id=item.item_id,
                    source_seq_start=item.source_seq_start,
                    source_seq_end=item.source_seq_end,
                    source_seqs=[int(seq) for seq in item.source_seqs],
                    conversation_speaker=item.speaker,
                    provider_speaker_id=provider_speaker_id,
                    content=parsed.content,
                    plain_text=parsed.plain_text,
                    cue_texts=parsed.cue_texts,
                    content_hash=content_hash,
                )
            )
        return result

    @staticmethod
    def _parse_content(content: str) -> ParsedTtsContent:
        normalized_content = (content or "").strip()
        cue_texts = [
            segment.strip()[1:-1].strip()
            for segment in _CUE_SEGMENT_PATTERN.findall(normalized_content)
            if segment.strip()[1:-1].strip()
        ]
        plain_text = _CUE_SEGMENT_PATTERN.sub(" ", normalized_content)
        plain_text = re.sub(r"\s+", " ", plain_text).strip()
        if not plain_text:
            raise ValueError("content must contain speech text")
        return ParsedTtsContent(
            content=normalized_content,
            plain_text=plain_text,
            cue_texts=cue_texts,
        )

    def _build_content_hash(
        self,
        *,
        parsed: ParsedTtsContent,
        provider_speaker_id: str,
        settings_value: TtsSettingsValue,
    ) -> str:
        payload = json.dumps(
            {
                "plain_text": parsed.plain_text,
                "cue_texts": parsed.cue_texts,
                "provider": self._provider.provider_name,
                "provider_speaker_id": provider_speaker_id,
                "format": settings_value.format,
                "emotion_scale": settings_value.emotion_scale,
                "speech_rate": settings_value.speech_rate,
                "loudness_rate": settings_value.loudness_rate,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _build_full_content_hash(
        self,
        *,
        provider: str,
        settings_value: TtsSettingsValue,
        items: list[StoredSynthesisItem],
    ) -> str:
        payload = json.dumps(
            {
                "provider": provider,
                "format": settings_value.format,
                "emotion_scale": settings_value.emotion_scale,
                "speech_rate": settings_value.speech_rate,
                "loudness_rate": settings_value.loudness_rate,
                "items": [
                    {
                        "source_item_id": item.source_item_id,
                        "conversation_speaker": item.conversation_speaker,
                        "provider_speaker_id": item.provider_speaker_id,
                        "content_hash": item.content_hash,
                    }
                    for item in items
                ],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _build_cache_key(provider: str, content_hash: str) -> str:
        return f"tts:clip:{provider}:{content_hash}"

    def _settings_value_from_model(
        self,
        *,
        session_id: str,
        model: SessionTtsSettingsModel | None,
    ) -> TtsSettingsValue:
        if model is None:
            return TtsSettingsValue(
                session_id=session_id,
                format=self._settings.TTS_DEFAULT_FORMAT,
                emotion_scale=float(self._settings.TTS_DEFAULT_EMOTION_SCALE),
                speech_rate=float(self._settings.TTS_DEFAULT_SPEECH_RATE),
                loudness_rate=float(self._settings.TTS_DEFAULT_LOUDNESS_RATE),
                speaker_mappings=[],
            )
        return TtsSettingsValue(
            session_id=session_id,
            format=str(model.format),
            emotion_scale=float(model.emotion_scale),
            speech_rate=float(model.speech_rate),
            loudness_rate=float(model.loudness_rate),
            speaker_mappings=[
                TtsSpeakerMapping(
                    conversation_speaker=str(item.get("conversation_speaker", "")).strip(),
                    provider_speaker_id=str(item.get("provider_speaker_id", "")).strip(),
                )
                for item in (model.speaker_mappings_json or [])
                if str(item.get("conversation_speaker", "")).strip()
                and str(item.get("provider_speaker_id", "")).strip()
            ],
        )

    @staticmethod
    def _to_settings_data(value: TtsSettingsValue) -> TtsSettingsData:
        return TtsSettingsData(
            session_id=value.session_id,
            format=value.format,
            emotion_scale=value.emotion_scale,
            speech_rate=value.speech_rate,
            loudness_rate=value.loudness_rate,
            speaker_mappings=[
                {
                    "conversation_speaker": item.conversation_speaker,
                    "provider_speaker_id": item.provider_speaker_id,
                }
                for item in value.speaker_mappings
            ],
        )

    def _to_synthesis_data(self, model: SpeechSynthesisModel) -> TtsSynthesisData:
        full_asset_url = (
            self._asset_service.build_asset_url(model.full_asset_object_key)
            if model.full_asset_object_key
            else None
        )
        items = [
            TtsSynthesisItemData.build(
                item_id=str(item.source_item_id),
                conversation_speaker=item.conversation_speaker,
                provider_speaker_id=item.provider_speaker_id,
                content=item.content,
                plain_text=item.plain_text,
                cue_texts=list(item.cue_texts),
                content_hash=item.content_hash,
                duration_ms=item.duration_ms,
                status=int(item.status),
            )
            for item in model.items
        ]
        return TtsSynthesisData.build(
            synthesis_id=self._format_public_synthesis_id(model.synthesis_id),
            session_id=str(model.session_id),
            provider=model.provider,
            full_asset_url=full_asset_url,
            full_duration_ms=model.full_duration_ms,
            item_count=model.item_count,
            completed_item_count=model.completed_item_count,
            failed_item_count=model.failed_item_count,
            status=int(model.status),
            error_code=model.error_code,
            error_message=model.error_message,
            created_at=model.created_at,
            updated_at=model.updated_at,
            items=items,
        )

    def _resolve_provider_speaker_id(
        self,
        *,
        conversation_speaker: str | None,
        settings_value: TtsSettingsValue,
        speakers: list[TtsSpeaker],
    ) -> str:
        normalized_conversation_speaker = (conversation_speaker or "Speaker").strip() or "Speaker"
        for item in settings_value.speaker_mappings:
            if item.conversation_speaker == normalized_conversation_speaker:
                return item.provider_speaker_id
        if not speakers:
            raise RuntimeError("No available tts speakers")
        return speakers[0].speaker_id

    def _validate_provider_speakers(self, speaker_mappings: list[TtsSpeakerMapping]) -> None:
        available_ids = {item.speaker_id for item in self._provider.get_speakers()}
        if not available_ids:
            return
        for item in speaker_mappings:
            if item.provider_speaker_id not in available_ids:
                raise ValueError(f"unsupported provider_speaker_id: {item.provider_speaker_id}")

    @staticmethod
    def _normalize_speaker_mappings(items: list) -> list[TtsSpeakerMapping]:
        normalized: list[TtsSpeakerMapping] = []
        seen: set[str] = set()
        for item in items:
            conversation_speaker = item.conversation_speaker.strip()
            provider_speaker_id = item.provider_speaker_id.strip()
            if not conversation_speaker or not provider_speaker_id:
                continue
            if conversation_speaker in seen:
                raise ValueError(f"duplicate conversation speaker mapping: {conversation_speaker}")
            seen.add(conversation_speaker)
            normalized.append(
                TtsSpeakerMapping(
                    conversation_speaker=conversation_speaker,
                    provider_speaker_id=provider_speaker_id,
                )
            )
        return normalized

    @staticmethod
    def _find_revision_item(*, revision: RevisionData, item_id: str) -> RevisionItemData:
        for item in revision.items:
            if item.item_id == item_id:
                return item
        raise ValueError("tts source item not found")

    def _register_job(self, session_id: str) -> str:
        token = uuid.uuid4().hex
        with self._job_tokens_lock:
            self._job_tokens[session_id] = token
        return token

    def _is_active_job(self, *, session_id: str, job_token: str) -> bool:
        with self._job_tokens_lock:
            return self._job_tokens.get(session_id) == job_token

    def _clear_job(self, *, session_id: str, job_token: str) -> None:
        with self._job_tokens_lock:
            if self._job_tokens.get(session_id) == job_token:
                self._job_tokens.pop(session_id, None)

    @staticmethod
    def _format_public_synthesis_id(raw_synthesis_id: str) -> str:
        return f"tts_{uuid.UUID(raw_synthesis_id).hex}"

    @staticmethod
    def _content_type_for_format(format_name: str) -> str:
        if format_name.lower() == "wav":
            return "audio/wav"
        return "audio/mpeg"

    @staticmethod
    def _sum_durations(values: list[int | None]) -> int | None:
        if not values or any(value is None for value in values):
            return None
        return sum(int(value) for value in values if value is not None)

    @staticmethod
    def _merge_audio_segments(*, format_name: str, audio_segments: list[bytes]) -> bytes:
        normalized_format = format_name.lower()
        if normalized_format != "wav":
            return b"".join(audio_segments)

        output = io.BytesIO()
        wav_params = None
        with wave.open(output, "wb") as target_wav:
            for segment in audio_segments:
                with wave.open(io.BytesIO(segment), "rb") as source_wav:
                    current_params = (
                        source_wav.getnchannels(),
                        source_wav.getsampwidth(),
                        source_wav.getframerate(),
                    )
                    if wav_params is None:
                        wav_params = current_params
                        target_wav.setnchannels(current_params[0])
                        target_wav.setsampwidth(current_params[1])
                        target_wav.setframerate(current_params[2])
                    elif wav_params != current_params:
                        raise RuntimeError("Cannot merge wav segments with different audio params")
                    target_wav.writeframes(source_wav.readframes(source_wav.getnframes()))
        return output.getvalue()

    @staticmethod
    def _replace_stored_item(
        item: StoredSynthesisItem,
        *,
        duration_ms: int | None,
        status: int,
        error_code: str | None,
        error_message: str | None,
    ) -> StoredSynthesisItem:
        return StoredSynthesisItem(
            source_item_id=item.source_item_id,
            source_seq_start=item.source_seq_start,
            source_seq_end=item.source_seq_end,
            source_seqs=list(item.source_seqs),
            conversation_speaker=item.conversation_speaker,
            provider_speaker_id=item.provider_speaker_id,
            content=item.content,
            plain_text=item.plain_text,
            cue_texts=list(item.cue_texts),
            content_hash=item.content_hash,
            duration_ms=duration_ms,
            status=status,
            error_code=error_code,
            error_message=error_message,
        )
