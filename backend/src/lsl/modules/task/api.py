from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Request

from lsl.modules.task.schema import (
    ApiResponse,
    CreateTaskRequest,
    TaskData,
    TaskListResponseData,
    TaskTranscriptData,
)
from lsl.modules.task.service import TaskService

router = APIRouter(prefix="/tasks", tags=["tasks"])


def get_task_service(request: Request) -> TaskService:
    service = getattr(request.app.state, "task_service", None)
    if service is None:
        raise HTTPException(status_code=500, detail="Task service is not initialized")
    return cast(TaskService, service)


@router.post("", response_model=ApiResponse[TaskData])
def create_task(
    payload: CreateTaskRequest,
    task_service: TaskService = Depends(get_task_service),
):
    try:
        task = task_service.create_task(
            object_key=payload.object_key,
            audio_url=payload.audio_url,
            language=payload.language,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ApiResponse(data=task)


@router.get("", response_model=ApiResponse[TaskListResponseData])
def list_tasks(
    limit: int = 20,
    status: int | None = None,
    category: str | None = None,
    entity_id: str | None = None,
    task_service: TaskService = Depends(get_task_service),
):
    try:
        items = task_service.list_tasks(
            limit=limit,
            status=status,
            category=category,
            entity_id=entity_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ApiResponse(data=TaskListResponseData(items=items))


@router.get("/{task_id}", response_model=ApiResponse[TaskData])
def get_task(
    task_id: str,
    refresh: bool = True,
    task_service: TaskService = Depends(get_task_service),
):
    try:
        task = task_service.get_task(task_id=task_id, auto_refresh=refresh)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ApiResponse(data=task)


@router.post("/{task_id}/refresh", response_model=ApiResponse[TaskData])
def refresh_task(
    task_id: str,
    task_service: TaskService = Depends(get_task_service),
):
    try:
        task = task_service.refresh_task(task_id=task_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ApiResponse(data=task)


@router.get("/{task_id}/transcript", response_model=ApiResponse[TaskTranscriptData])
def get_task_transcript(
    task_id: str,
    include_raw: bool = False,
    task_service: TaskService = Depends(get_task_service),
):
    try:
        transcript = task_service.get_transcript(task_id=task_id, include_raw=include_raw)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ApiResponse(data=transcript)
