from __future__ import annotations

import uuid
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session as OrmSession
from sqlalchemy.orm import selectinload, sessionmaker

from lsl.modules.tts.model import (
    SessionTtsSettingsModel,
    SpeechSynthesisItemModel,
    SpeechSynthesisModel,
)
from lsl.modules.tts.types import StoredSynthesisItem, TtsSynthesisStatus


class TtsRepository:
    def __init__(self, session_factory: sessionmaker[OrmSession]) -> None:
        self._session_factory = session_factory

    @contextmanager
    def _session_scope(self) -> Iterator[OrmSession]:
        db = self._session_factory()
        try:
            yield db
        finally:
            db.close()

    def get_settings_by_session_id(self, session_id: str) -> SessionTtsSettingsModel | None:
        normalized_session_id = self._parse_uuid_str(session_id)
        if normalized_session_id is None:
            return None

        try:
            with self._session_scope() as db:
                return db.get(SessionTtsSettingsModel, normalized_session_id)
        except SQLAlchemyError as exc:  # pragma: no cover
            raise RuntimeError(f"Failed to query TTS settings: {exc}") from exc

    def save_settings(
        self,
        *,
        session_id: str,
        format: str,
        emotion_scale: float,
        speech_rate: float,
        loudness_rate: float,
        speaker_mappings_json: list[dict[str, str]],
    ) -> SessionTtsSettingsModel:
        normalized_session_id = self._require_uuid(session_id, field_name="session_id")
        try:
            with self._session_scope() as db:
                model = db.get(SessionTtsSettingsModel, normalized_session_id)
                if model is None:
                    model = SessionTtsSettingsModel(session_id=normalized_session_id)
                    db.add(model)
                model.format = format
                model.emotion_scale = float(emotion_scale)
                model.speech_rate = float(speech_rate)
                model.loudness_rate = float(loudness_rate)
                model.speaker_mappings_json = speaker_mappings_json
                db.commit()
                db.refresh(model)
                return model
        except SQLAlchemyError as exc:  # pragma: no cover
            raise RuntimeError(f"Failed to save TTS settings: {exc}") from exc

    def get_synthesis_by_session_id(self, session_id: str) -> SpeechSynthesisModel | None:
        normalized_session_id = self._parse_uuid_str(session_id)
        if normalized_session_id is None:
            return None

        stmt = (
            select(SpeechSynthesisModel)
            .options(selectinload(SpeechSynthesisModel.items))
            .where(SpeechSynthesisModel.session_id == normalized_session_id)
            .limit(1)
        )
        try:
            with self._session_scope() as db:
                return db.execute(stmt).scalar_one_or_none()
        except SQLAlchemyError as exc:  # pragma: no cover
            raise RuntimeError(f"Failed to query speech synthesis: {exc}") from exc

    def save_synthesis(
        self,
        *,
        session_id: str,
        provider: str,
        full_content_hash: str,
        status: int,
        items: list[StoredSynthesisItem],
        full_asset_object_key: str | None = None,
        full_duration_ms: int | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> SpeechSynthesisModel:
        normalized_session_id = self._require_uuid(session_id, field_name="session_id")
        self._validate_items(items)
        try:
            with self._session_scope() as db:
                stmt = (
                    select(SpeechSynthesisModel)
                    .options(selectinload(SpeechSynthesisModel.items))
                    .where(SpeechSynthesisModel.session_id == normalized_session_id)
                    .limit(1)
                )
                model = db.execute(stmt).scalar_one_or_none()
                if model is None:
                    model = SpeechSynthesisModel(
                        synthesis_id=str(uuid.uuid4()),
                        session_id=normalized_session_id,
                    )
                    db.add(model)

                model.provider = provider
                model.full_content_hash = full_content_hash
                model.status = int(status)
                model.full_asset_object_key = full_asset_object_key
                model.full_duration_ms = full_duration_ms
                model.error_code = error_code
                model.error_message = error_message
                model.item_count = len(items)
                model.completed_item_count = sum(
                    1 for item in items if int(item.status) == int(TtsSynthesisStatus.COMPLETED)
                )
                model.failed_item_count = sum(
                    1 for item in items if int(item.status) == int(TtsSynthesisStatus.FAILED)
                )

                existing_items_by_source_id = {
                    str(existing_item.source_item_id): existing_item
                    for existing_item in model.items
                }
                incoming_source_ids = {str(item.source_item_id) for item in items}
                for existing_source_id, existing_item in list(existing_items_by_source_id.items()):
                    if existing_source_id not in incoming_source_ids:
                        model.items.remove(existing_item)

                for item in items:
                    source_item_id = self._require_uuid(item.source_item_id, field_name="source_item_id")
                    model_item = existing_items_by_source_id.get(source_item_id)
                    if model_item is None:
                        model_item = SpeechSynthesisItemModel(
                            tts_item_id=str(uuid.uuid4()),
                            source_item_id=source_item_id,
                            source_seq_start=int(item.source_seq_start),
                            source_seq_end=int(item.source_seq_end),
                            source_seqs=[int(seq) for seq in item.source_seqs],
                            conversation_speaker=item.conversation_speaker,
                            provider_speaker_id=item.provider_speaker_id,
                            content=item.content,
                            plain_text=item.plain_text,
                            cue_texts=list(item.cue_texts),
                            content_hash=item.content_hash,
                            duration_ms=item.duration_ms,
                            status=int(item.status),
                            error_code=item.error_code,
                            error_message=item.error_message,
                        )
                        model.items.append(model_item)
                        continue

                    model_item.source_item_id = source_item_id
                    model_item.source_seq_start = int(item.source_seq_start)
                    model_item.source_seq_end = int(item.source_seq_end)
                    model_item.source_seqs = [int(seq) for seq in item.source_seqs]
                    model_item.conversation_speaker = item.conversation_speaker
                    model_item.provider_speaker_id = item.provider_speaker_id
                    model_item.content = item.content
                    model_item.plain_text = item.plain_text
                    model_item.cue_texts = list(item.cue_texts)
                    model_item.content_hash = item.content_hash
                    model_item.duration_ms = item.duration_ms
                    model_item.status = int(item.status)
                    model_item.error_code = item.error_code
                    model_item.error_message = item.error_message

                db.commit()
                db.refresh(model)
                _ = list(model.items)
                return model
        except SQLAlchemyError as exc:  # pragma: no cover
            raise RuntimeError(f"Failed to save speech synthesis: {exc}") from exc

    @staticmethod
    def _parse_uuid_str(value: str) -> str | None:
        try:
            return str(uuid.UUID(value))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _require_uuid(value: str, *, field_name: str) -> str:
        parsed = TtsRepository._parse_uuid_str(value)
        if parsed is None:
            raise RuntimeError(f"Invalid {field_name}")
        return parsed

    @staticmethod
    def _validate_items(items: list[StoredSynthesisItem]) -> None:
        seen_source_ids: set[str] = set()
        for item in items:
            source_item_id = str(item.source_item_id)
            if source_item_id in seen_source_ids:
                raise RuntimeError(f"Duplicate source_item_id in speech synthesis items: {source_item_id}")
            seen_source_ids.add(source_item_id)
            source_seqs = [int(seq) for seq in item.source_seqs]
            if not source_seqs:
                raise RuntimeError("Speech synthesis item source_seqs cannot be empty")
