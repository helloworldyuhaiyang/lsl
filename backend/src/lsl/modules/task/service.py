from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from lsl.modules.task.repo import TaskRepository
from lsl.modules.task.schema import TaskData, TaskTranscriptData, TaskTranscriptUtterance
from lsl.modules.task.types import (
    AsrJobRef,
    AsrJobStatus,
    AsrProvider,
    AsrSubmitRequest,
    TaskStatus,
)

logger = logging.getLogger(__name__)

class TaskService:
    """
    任务编排层：
    - 管理任务状态流转（uploaded -> transcribing -> completed/failed）
    - 协调 ASR provider 与持久化层
    - 对外返回稳定的 TaskData / Transcript 结构
    """

    def __init__(
        self,
        *,
        repository: TaskRepository,
        asr_provider: AsrProvider,
    ) -> None:
        self._repository = repository
        self._asr_provider = asr_provider

    def create_task(self, *, object_key: str, audio_url: str, language: str | None = None) -> TaskData:
        # 统一 object_key 规范，避免同一资源因前后斜杠差异导致重复任务。
        object_key = object_key.strip().lstrip("/")
        if not object_key:
            raise ValueError("object_key is required")
        audio_url = audio_url.strip()
        if not audio_url:
            raise ValueError("audio_url is required")

        # 以 object_key 做幂等：同一音频重复提交时直接返回既有任务。
        existing = self._repository.get_task_by_object_key(object_key)
        if existing is not None:
            return TaskData.from_row(existing)

        task_id = str(uuid.uuid4())
        provider_name = self._provider_name()
        self._repository.create_task(
            task_id=task_id,
            object_key=object_key,
            audio_url=audio_url,
            language=language,
            provider=provider_name,
        )

        try:
            # 先创建本地任务，再提交到 provider，确保提交失败也可追踪失败原因。
            submit_result = self._asr_provider.submit(
                AsrSubmitRequest(
                    task_id=task_id,
                    audio_url=audio_url,
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
            # provider 未接入时标记为 failed，便于前端明确展示不可用原因。
            self._repository.mark_failed(
                task_id=task_id,
                error_code="PROVIDER_NOT_IMPLEMENTED",
                error_message=str(exc),
                provider_status_code=None,
                provider_message=None,
                x_tt_logid=None,
            )
        except Exception as exc:
            # 提交阶段兜底异常：持久化为 failed，避免任务悬空。
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

        # 仅在 transcribing 状态触发自动刷新，避免对终态任务产生无意义查询。
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
        # 非进行中任务直接返回，保证 refresh 是幂等、安全的。
        if int(row["status"]) != int(TaskStatus.TRANSCRIBING):
            return TaskData.from_row(row)

        provider_request_id = row.get("provider_request_id")
        if not provider_request_id:
            # transcribing 却缺少 provider_request_id 说明数据已不一致，直接失败止损。
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
            # 按 provider 回包驱动状态机迁移。
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
                    # 成功态必须带原始结果；否则视为非法回包。
                    self._repository.mark_failed(
                        task_id=task_id,
                        error_code="INVALID_PROVIDER_RESULT",
                        error_message="raw_result is missing on succeeded status",
                        provider_status_code=query_result.provider_status_code,
                        provider_message=query_result.provider_message,
                        x_tt_logid=query_result.x_tt_logid,
                    )
                else:
                    # 落库转写明细并将任务置为 completed。
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
        
        logger.info("Refreshed task %s: provider_status=%s, provider_message=%s",
            task_id,
            latest.get("provider_status_code"),
            latest.get("provider_message"),
        )
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

    def list_tasks_by_ids(self, *, task_ids: list[str], auto_refresh: bool = False) -> dict[str, TaskData]:
        normalized = sorted({item.strip() for item in task_ids if item and item.strip()})
        if not normalized:
            return {}

        rows = self._repository.list_tasks_by_ids(task_ids=normalized)
        items = {str(item["task_id"]): TaskData.from_row(item) for item in rows}

        if not auto_refresh:
            return items

        refreshed: dict[str, TaskData] = {}
        for task_id, item in items.items():
            if item.status == int(TaskStatus.TRANSCRIBING):
                refreshed[task_id] = self.get_task(task_id=task_id, auto_refresh=True)
            else:
                refreshed[task_id] = item
        return refreshed

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
        # 对异常/脏数据采取 允许轮询 的容错策略，避免任务长期卡住。
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

    def _provider_name(self) -> str:
        return getattr(self._asr_provider, "provider_name", "unknown")
