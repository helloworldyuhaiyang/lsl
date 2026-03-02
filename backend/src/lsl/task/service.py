from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from lsl.asr.provider import (
    AsrJobRef,
    AsrJobStatus,
    AsrProvider,
    AsrSubmitRequest,
)
from lsl.config import Settings
from lsl.task.repository import TaskRepository
from lsl.task.schemas import TaskData, TaskTranscriptData, TaskTranscriptUtterance
from lsl.task.status import TaskStatus


class TaskService:
    def __init__(
        self,
        *,
        settings: Settings,
        repository: TaskRepository,
        asr_provider: AsrProvider,
    ) -> None:
        self._settings = settings
        self._repository = repository
        self._asr_provider = asr_provider

    def create_task(self, *, object_key: str, language: str | None = None) -> TaskData:
        object_key = object_key.strip().lstrip("/")
        if not object_key:
            raise ValueError("object_key is required")

        existing = self._repository.get_task_by_object_key(object_key)
        if existing is not None:
            return TaskData.from_row(existing)

        task_id = str(uuid.uuid4())
        provider_name = self._provider_name()
        self._repository.create_task(
            task_id=task_id,
            object_key=object_key,
            language=language,
            provider=provider_name,
        )

        try:
            submit_result = self._asr_provider.submit(
                AsrSubmitRequest(
                    task_id=task_id,
                    audio_url=self._build_asset_url(object_key),
                    language=language,
                )
            )
            self._repository.mark_submitted(
                task_id=task_id,
                provider_request_id=submit_result.provider_request_id,
                provider_resource_id=submit_result.provider_resource_id,
                x_tt_logid=submit_result.x_tt_logid,
                next_poll_at=self._next_poll_time(poll_count=0),
            )
        except NotImplementedError as exc:
            self._repository.mark_failed(
                task_id=task_id,
                error_code="PROVIDER_NOT_IMPLEMENTED",
                error_message=str(exc),
                provider_status_code=None,
                provider_message=None,
                x_tt_logid=None,
            )
        except Exception as exc:
            self._repository.mark_failed(
                task_id=task_id,
                error_code="PROVIDER_SUBMIT_ERROR",
                error_message=str(exc),
                provider_status_code=None,
                provider_message=None,
                x_tt_logid=None,
            )

        row = self._repository.get_task_by_id(task_id)
        if row is None:
            raise RuntimeError("Task is missing after creation")
        return TaskData.from_row(row)

    def get_task(self, *, task_id: str, auto_refresh: bool = True) -> TaskData:
        row = self._repository.get_task_by_id(task_id)
        if row is None:
            raise ValueError("task not found")

        if auto_refresh and int(row["status"]) == int(TaskStatus.TRANSCRIBING):
            next_poll_at = row.get("next_poll_at")
            if self._should_poll(next_poll_at):
                self.refresh_task(task_id=task_id)
                row = self._repository.get_task_by_id(task_id)
                if row is None:
                    raise RuntimeError("Task is missing after refresh")
        return TaskData.from_row(row)

    def refresh_task(self, *, task_id: str) -> TaskData:
        row = self._repository.get_task_by_id(task_id)
        if row is None:
            raise ValueError("task not found")
        if int(row["status"]) != int(TaskStatus.TRANSCRIBING):
            return TaskData.from_row(row)

        provider_request_id = row.get("provider_request_id")
        if not provider_request_id:
            self._repository.mark_failed(
                task_id=task_id,
                error_code="MISSING_PROVIDER_REQUEST_ID",
                error_message="provider_request_id is missing",
                provider_status_code=None,
                provider_message=None,
                x_tt_logid=None,
            )
            latest = self._repository.get_task_by_id(task_id)
            if latest is None:
                raise RuntimeError("Task is missing after refresh failure")
            return TaskData.from_row(latest)

        query_ref = AsrJobRef(
            task_id=task_id,
            provider=row.get("provider") or self._provider_name(),
            provider_request_id=provider_request_id,
            provider_resource_id=row.get("provider_resource_id"),
            x_tt_logid=row.get("x_tt_logid"),
        )

        try:
            query_result = self._asr_provider.query(query_ref)
        except NotImplementedError as exc:
            self._repository.mark_failed(
                task_id=task_id,
                error_code="PROVIDER_NOT_IMPLEMENTED",
                error_message=str(exc),
                provider_status_code=None,
                provider_message=None,
                x_tt_logid=None,
            )
        except Exception as exc:
            self._repository.mark_failed(
                task_id=task_id,
                error_code="PROVIDER_QUERY_ERROR",
                error_message=str(exc),
                provider_status_code=None,
                provider_message=None,
                x_tt_logid=None,
            )
        else:
            if query_result.status in (AsrJobStatus.QUEUED, AsrJobStatus.PROCESSING):
                self._repository.mark_processing(
                    task_id=task_id,
                    provider_status_code=query_result.provider_status_code,
                    provider_message=query_result.provider_message,
                    x_tt_logid=query_result.x_tt_logid,
                    next_poll_at=self._next_poll_time(poll_count=int(row.get("poll_count", 0)) + 1),
                )
            elif query_result.status == AsrJobStatus.FAILED:
                self._repository.mark_failed(
                    task_id=task_id,
                    error_code=query_result.error_code or "PROVIDER_TASK_FAILED",
                    error_message=query_result.error_message or query_result.provider_message,
                    provider_status_code=query_result.provider_status_code,
                    provider_message=query_result.provider_message,
                    x_tt_logid=query_result.x_tt_logid,
                )
            elif query_result.status == AsrJobStatus.SUCCEEDED:
                if query_result.raw_result is None:
                    self._repository.mark_failed(
                        task_id=task_id,
                        error_code="INVALID_PROVIDER_RESULT",
                        error_message="raw_result is missing on succeeded status",
                        provider_status_code=query_result.provider_status_code,
                        provider_message=query_result.provider_message,
                        x_tt_logid=query_result.x_tt_logid,
                    )
                else:
                    utterances = [item.model_dump() for item in query_result.utterances]
                    self._repository.mark_completed_with_result(
                        task_id=task_id,
                        provider=row.get("provider") or self._provider_name(),
                        duration_ms=query_result.duration_ms,
                        full_text=query_result.full_text,
                        raw_result_json=query_result.raw_result,
                        utterances=utterances,
                        provider_status_code=query_result.provider_status_code,
                        provider_message=query_result.provider_message,
                        x_tt_logid=query_result.x_tt_logid,
                    )

        latest = self._repository.get_task_by_id(task_id)
        if latest is None:
            raise RuntimeError("Task is missing after refresh")
        return TaskData.from_row(latest)

    def list_tasks(
        self,
        *,
        limit: int = 20,
        status: int | None = None,
        category: str | None = None,
        entity_id: str | None = None,
    ) -> list[TaskData]:
        if limit <= 0:
            raise ValueError("limit must be greater than 0")
        if limit > 100:
            raise ValueError("limit must be less than or equal to 100")
        rows = self._repository.list_tasks(
            limit=limit,
            status=status,
            category=category,
            entity_id=entity_id,
        )
        return [TaskData.from_row(item) for item in rows]

    def get_transcript(self, *, task_id: str, include_raw: bool = False) -> TaskTranscriptData:
        task_row = self._repository.get_task_by_id(task_id)
        if task_row is None:
            raise ValueError("task not found")
        if int(task_row["status"]) != int(TaskStatus.COMPLETED):
            raise ValueError("task is not completed")

        transcript = self._repository.get_transcript(task_id=task_id)
        if transcript is None:
            raise ValueError("transcript not found")

        utterances = [
            TaskTranscriptUtterance(
                seq=int(item["seq"]),
                text=item["text"],
                speaker=item.get("speaker"),
                start_time=int(item["start_time"]),
                end_time=int(item["end_time"]),
                additions=item.get("additions_json") or {},
            )
            for item in transcript["utterances"]
        ]
        return TaskTranscriptData(
            task_id=task_id,
            duration_ms=transcript.get("duration_ms"),
            full_text=transcript.get("full_text"),
            utterances=utterances,
            raw_result=transcript.get("raw_result_json") if include_raw else None,
        )

    @staticmethod
    def _should_poll(next_poll_at: Any) -> bool:
        if next_poll_at is None:
            return True
        if not isinstance(next_poll_at, datetime):
            return True
        if next_poll_at.tzinfo is None:
            next_poll_at = next_poll_at.replace(tzinfo=timezone.utc)
        return next_poll_at <= datetime.now(timezone.utc)

    @staticmethod
    def _next_poll_time(*, poll_count: int) -> datetime:
        # 轻量退避：2s -> 4s -> 6s ... 上限 15s
        interval_sec = min(2 * max(1, poll_count + 1), 15)
        return datetime.now(timezone.utc) + timedelta(seconds=interval_sec)

    def _build_asset_url(self, object_key: str) -> str:
        if not self._settings.ASSET_BASE_URL:
            raise RuntimeError("ASSET_BASE_URL is required for task submit")
        return f"{self._settings.ASSET_BASE_URL.rstrip('/')}/{object_key}"

    def _provider_name(self) -> str:
        return getattr(self._asr_provider, "provider_name", "unknown")
