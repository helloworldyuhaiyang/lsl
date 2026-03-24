from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator
import uuid

from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session as OrmSession
from sqlalchemy.orm import sessionmaker

from lsl.modules.task.model import AsrResultModel, AsrUtteranceModel, TaskModel


class TaskRepository:
    def __init__(self, session_factory: sessionmaker[OrmSession]) -> None:
        self._session_factory = session_factory

    @contextmanager
    def _session_scope(self) -> Iterator[OrmSession]:
        db = self._session_factory()
        try:
            yield db
        finally:
            db.close()

    def create_task(
        self,
        *,
        task_id: str,
        object_key: str,
        audio_url: str,
        language: str | None,
        provider: str,
    ) -> None:
        normalized_task_id = self._require_uuid(task_id, field_name="task_id")
        model = TaskModel(
            task_id=normalized_task_id,
            object_key=object_key,
            audio_url=audio_url,
            status=0,
            language=language,
            provider=provider,
        )
        try:
            with self._session_scope() as db:
                db.add(model)
                db.commit()
        except SQLAlchemyError as exc:  # pragma: no cover
            raise RuntimeError(f"Failed to create task: {exc}") from exc

    def create_completed_text_task(
        self,
        *,
        task_id: str,
        object_key: str,
        audio_url: str,
        language: str | None,
        provider: str,
        duration_ms: int,
        full_text: str,
        raw_result_json: dict[str, Any],
        utterances: list[dict[str, Any]],
    ) -> None:
        normalized_task_id = self._require_uuid(task_id, field_name="task_id")
        now = datetime.now(timezone.utc)
        task_model = TaskModel(
            task_id=normalized_task_id,
            object_key=object_key,
            audio_url=audio_url,
            duration_ms=duration_ms,
            status=3,
            language=language,
            provider=provider,
            provider_status_code="completed",
            provider_message="synthetic_text_task",
            last_polled_at=now,
            next_poll_at=None,
        )
        result_model = AsrResultModel(
            task_id=normalized_task_id,
            provider=provider,
            duration_ms=duration_ms,
            full_text=full_text,
            raw_result_json=raw_result_json,
        )
        try:
            with self._session_scope() as db:
                db.add(task_model)
                db.add(result_model)
                for item in utterances:
                    db.add(
                        AsrUtteranceModel(
                            task_id=normalized_task_id,
                            seq=int(item["seq"]),
                            text=item["text"],
                            speaker=item.get("speaker"),
                            start_time=int(item["start_time"]),
                            end_time=int(item["end_time"]),
                            additions_json=item.get("additions") or {},
                        )
                    )
                db.commit()
        except SQLAlchemyError as exc:  # pragma: no cover
            raise RuntimeError(f"Failed to create completed text task: {exc}") from exc

    def get_task_by_id(self, task_id: str) -> dict[str, Any] | None:
        normalized_task_id = self._parse_uuid_str(task_id)
        if normalized_task_id is None:
            return None

        stmt = select(TaskModel).where(TaskModel.task_id == normalized_task_id).limit(1)
        try:
            with self._session_scope() as db:
                model = db.execute(stmt).scalar_one_or_none()
                return self._task_to_row(model) if model is not None else None
        except SQLAlchemyError as exc:  # pragma: no cover
            raise RuntimeError(f"Failed to query task by id: {exc}") from exc

    def get_task_by_object_key(self, object_key: str) -> dict[str, Any] | None:
        stmt = select(TaskModel).where(TaskModel.object_key == object_key).limit(1)
        try:
            with self._session_scope() as db:
                model = db.execute(stmt).scalar_one_or_none()
                return self._task_to_row(model) if model is not None else None
        except SQLAlchemyError as exc:  # pragma: no cover
            raise RuntimeError(f"Failed to query task by object_key: {exc}") from exc

    def list_tasks_by_ids(self, *, task_ids: list[str]) -> list[dict[str, Any]]:
        normalized_task_ids = [self._parse_uuid_str(item) for item in task_ids]
        filtered_task_ids = [item for item in normalized_task_ids if item is not None]
        if not filtered_task_ids:
            return []

        stmt = select(TaskModel).where(TaskModel.task_id.in_(filtered_task_ids))
        try:
            with self._session_scope() as db:
                rows = db.execute(stmt).scalars().all()
                return [self._task_to_row(model) for model in rows]
        except SQLAlchemyError as exc:  # pragma: no cover
            raise RuntimeError(f"Failed to query tasks by ids: {exc}") from exc

    def list_tasks(
        self,
        *,
        limit: int,
        status: int | None = None,
        category: str | None = None,
        entity_id: str | None = None,
    ) -> list[dict[str, Any]]:
        stmt = select(TaskModel)

        if status is not None:
            stmt = stmt.where(TaskModel.status == int(status))

        if category and entity_id:
            stmt = stmt.where(TaskModel.object_key.like(f"{category}/{entity_id}/%"))
        elif category:
            stmt = stmt.where(TaskModel.object_key.like(f"{category}/%"))
        elif entity_id:
            stmt = stmt.where(TaskModel.object_key.like(f"%/{entity_id}/%"))

        stmt = stmt.order_by(TaskModel.created_at.desc()).limit(limit)

        try:
            with self._session_scope() as db:
                rows = db.execute(stmt).scalars().all()
                return [self._task_to_row(model) for model in rows]
        except SQLAlchemyError as exc:  # pragma: no cover
            raise RuntimeError(f"Failed to list tasks: {exc}") from exc

    def mark_submitted(
        self,
        *,
        task_id: str,
        provider_request_id: str,
        provider_resource_id: str | None,
        x_tt_logid: str | None,
        next_poll_at: datetime,
    ) -> None:
        try:
            with self._session_scope() as db:
                model = self._get_required_task(db, task_id)
                model.status = 1
                model.provider_request_id = provider_request_id
                model.provider_resource_id = provider_resource_id
                model.x_tt_logid = x_tt_logid
                model.duration_ms = None
                model.provider_status_code = None
                model.provider_message = None
                model.error_code = None
                model.error_message = None
                model.poll_count = 0
                model.last_polled_at = None
                model.next_poll_at = next_poll_at
                db.commit()
        except SQLAlchemyError as exc:  # pragma: no cover
            raise RuntimeError(f"Failed to mark task as submitted: {exc}") from exc

    def mark_processing(
        self,
        *,
        task_id: str,
        provider_status_code: str | None,
        provider_message: str | None,
        x_tt_logid: str | None,
        next_poll_at: datetime,
    ) -> None:
        try:
            with self._session_scope() as db:
                model = self._get_required_task(db, task_id)
                model.status = 1
                model.provider_status_code = provider_status_code
                model.provider_message = provider_message
                model.x_tt_logid = x_tt_logid or model.x_tt_logid
                model.poll_count = int(model.poll_count) + 1
                model.last_polled_at = datetime.now(timezone.utc)
                model.next_poll_at = next_poll_at
                db.commit()
        except SQLAlchemyError as exc:  # pragma: no cover
            raise RuntimeError(f"Failed to mark task as processing: {exc}") from exc

    def mark_failed(
        self,
        *,
        task_id: str,
        error_code: str | None,
        error_message: str | None,
        provider_status_code: str | None,
        provider_message: str | None,
        x_tt_logid: str | None,
    ) -> None:
        try:
            with self._session_scope() as db:
                model = self._get_required_task(db, task_id)
                model.status = 4
                model.error_code = error_code
                model.error_message = error_message
                model.provider_status_code = provider_status_code
                model.provider_message = provider_message
                model.x_tt_logid = x_tt_logid or model.x_tt_logid
                model.duration_ms = None
                model.last_polled_at = datetime.now(timezone.utc)
                model.next_poll_at = None
                db.commit()
        except SQLAlchemyError as exc:  # pragma: no cover
            raise RuntimeError(f"Failed to mark task as failed: {exc}") from exc

    def reset_for_retry(self, *, task_id: str) -> None:
        try:
            with self._session_scope() as db:
                model = self._get_required_task(db, task_id)
                model.status = 0
                model.provider_request_id = None
                model.provider_resource_id = None
                model.provider_status_code = None
                model.provider_message = None
                model.duration_ms = None
                model.error_code = None
                model.error_message = None
                model.poll_count = 0
                model.last_polled_at = None
                model.next_poll_at = None
                db.commit()
        except SQLAlchemyError as exc:  # pragma: no cover
            raise RuntimeError(f"Failed to reset task for retry: {exc}") from exc

    def mark_completed_with_result(
        self,
        *,
        task_id: str,
        provider: str,
        duration_ms: int | None,
        full_text: str | None,
        raw_result_json: dict[str, Any],
        utterances: list[dict[str, Any]],
        provider_status_code: str | None,
        provider_message: str | None,
        x_tt_logid: str | None,
    ) -> None:
        normalized_task_id = self._require_uuid(task_id, field_name="task_id")
        try:
            with self._session_scope() as db:
                task_model = self._get_required_task(db, normalized_task_id)

                result_model = db.get(AsrResultModel, normalized_task_id)
                if result_model is None:
                    result_model = AsrResultModel(task_id=normalized_task_id)
                    db.add(result_model)

                result_model.provider = provider
                result_model.duration_ms = duration_ms
                result_model.full_text = full_text
                result_model.raw_result_json = raw_result_json

                db.execute(delete(AsrUtteranceModel).where(AsrUtteranceModel.task_id == normalized_task_id))
                for item in utterances:
                    db.add(
                        AsrUtteranceModel(
                            task_id=normalized_task_id,
                            seq=int(item["seq"]),
                            text=item["text"],
                            speaker=item.get("speaker"),
                            start_time=int(item["start_time"]),
                            end_time=int(item["end_time"]),
                            additions_json=item.get("additions", {}),
                        )
                    )

                task_model.status = 3
                task_model.duration_ms = duration_ms
                task_model.provider_status_code = provider_status_code
                task_model.provider_message = provider_message
                task_model.x_tt_logid = x_tt_logid or task_model.x_tt_logid
                task_model.error_code = None
                task_model.error_message = None
                task_model.last_polled_at = datetime.now(timezone.utc)
                task_model.next_poll_at = None
                db.commit()
        except SQLAlchemyError as exc:  # pragma: no cover
            raise RuntimeError(f"Failed to persist ASR result: {exc}") from exc

    def get_transcript(self, *, task_id: str) -> dict[str, Any] | None:
        normalized_task_id = self._parse_uuid_str(task_id)
        if normalized_task_id is None:
            return None

        result_stmt = select(AsrResultModel).where(AsrResultModel.task_id == normalized_task_id).limit(1)
        utterance_stmt = (
            select(AsrUtteranceModel)
            .where(AsrUtteranceModel.task_id == normalized_task_id)
            .order_by(AsrUtteranceModel.seq.asc())
        )
        try:
            with self._session_scope() as db:
                result_model = db.execute(result_stmt).scalar_one_or_none()
                if result_model is None:
                    return None
                utterances = db.execute(utterance_stmt).scalars().all()
                return {
                    "duration_ms": result_model.duration_ms,
                    "full_text": result_model.full_text,
                    "raw_result_json": result_model.raw_result_json,
                    "utterances": [self._utterance_to_row(item) for item in utterances],
                }
        except SQLAlchemyError as exc:  # pragma: no cover
            raise RuntimeError(f"Failed to fetch transcript: {exc}") from exc

    def _get_required_task(self, db: OrmSession, task_id: str) -> TaskModel:
        normalized_task_id = self._require_uuid(task_id, field_name="task_id")
        model = db.get(TaskModel, normalized_task_id)
        if model is None:
            raise RuntimeError("Task not found")
        return model

    @staticmethod
    def _task_to_row(model: TaskModel) -> dict[str, Any]:
        return {
            "task_id": model.task_id,
            "object_key": model.object_key,
            "audio_url": model.audio_url,
            "duration_ms": model.duration_ms,
            "status": int(model.status),
            "language": model.language,
            "provider": model.provider,
            "provider_request_id": model.provider_request_id,
            "provider_resource_id": model.provider_resource_id,
            "x_tt_logid": model.x_tt_logid,
            "provider_status_code": model.provider_status_code,
            "provider_message": model.provider_message,
            "error_code": model.error_code,
            "error_message": model.error_message,
            "poll_count": int(model.poll_count),
            "last_polled_at": model.last_polled_at,
            "next_poll_at": model.next_poll_at,
            "created_at": model.created_at,
            "updated_at": model.updated_at,
        }

    @staticmethod
    def _utterance_to_row(model: AsrUtteranceModel) -> dict[str, Any]:
        return {
            "seq": int(model.seq),
            "text": model.text,
            "speaker": model.speaker,
            "start_time": int(model.start_time),
            "end_time": int(model.end_time),
            "additions_json": model.additions_json or {},
        }

    @staticmethod
    def _parse_uuid_str(value: str) -> str | None:
        try:
            return uuid.UUID(value).hex
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _require_uuid(value: str, *, field_name: str) -> str:
        parsed = TaskRepository._parse_uuid_str(value)
        if parsed is None:
            raise RuntimeError(f"Invalid {field_name}")
        return parsed
