from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, cast

from fastapi import Depends, FastAPI, HTTPException, Request
from datetime import timedelta

from lsl.asr import create_asr_provider
from lsl.config import Settings
from lsl.asset import AssetService
from lsl.asset.schemas import (
    ApiResponse,
    AssetListItemData,
    AssetListResponseData,
    CompleteUploadRequest,
    CompleteUploadResponseData,
    UploadUrlRequest,
    UploadUrlResponseData,
)
from lsl.asset.factory import create_storage_provider
from lsl.asset.repository import AssetRepository
from lsl.task import TaskRepository, TaskService
from lsl.task.schemas import (
    CreateTaskRequest,
    TaskData,
    TaskListResponseData,
    TaskTranscriptData,
)

if TYPE_CHECKING:
    from psycopg_pool import ConnectionPool

LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(pathname)s:%(lineno)d %(message)s"

if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,
        format=LOG_FORMAT,
    )
else:
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    formatter = logging.Formatter(LOG_FORMAT)
    for handler in root_logger.handlers:
        handler.setFormatter(formatter)

settings = Settings.from_env()

storage = create_storage_provider(settings)
asr_provider = create_asr_provider(settings)


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool: ConnectionPool | None = None
    asset_repository: AssetRepository | None = None
    task_repository: TaskRepository | None = None

    if settings.DATABASE_URL:
        try:
            from psycopg_pool import ConnectionPool
        except ImportError as exc:
            raise RuntimeError(
                "psycopg_pool is required. Run: uv pip install psycopg-pool"
            ) from exc

        pool = ConnectionPool(
            conninfo=settings.DATABASE_URL,
            min_size=settings.DB_POOL_MIN_SIZE,
            max_size=settings.DB_POOL_MAX_SIZE,
            timeout=settings.DB_POOL_TIMEOUT,
            open=False,
        )
        pool.open(wait=True)
        asset_repository = AssetRepository(pool)
        task_repository = TaskRepository(pool)

    app.state.asset_service = AssetService(
        settings=settings,
        storage=storage,
        repository=asset_repository,
    )
    app.state.task_service = (
        TaskService(
            settings=settings,
            repository=task_repository,
            asr_provider=asr_provider,
        )
        if task_repository is not None
        else None
    )
    app.state.db_pool = pool

    try:
        yield
    finally:
        if pool is not None:
            pool.close()


app = FastAPI(title="LSL", lifespan=lifespan)


def get_asset_service(request: Request) -> AssetService:
    service = getattr(request.app.state, "asset_service", None)
    if service is None:
        raise HTTPException(status_code=500, detail="Asset service is not initialized")
    return cast(AssetService, service)


def get_task_service(request: Request) -> TaskService:
    service = getattr(request.app.state, "task_service", None)
    if service is None:
        raise HTTPException(status_code=500, detail="Task service is not initialized")
    return cast(TaskService, service)


@app.get("/health", response_model=ApiResponse[dict[str, str]])
def health():
    return ApiResponse(data={"status": "ok"})


@app.post("/assets/upload-url", response_model=ApiResponse[UploadUrlResponseData])
def generate_upload_url(
    payload: UploadUrlRequest,
    asset_service: AssetService = Depends(get_asset_service),
):
    """
    生成上传用 Presigned URL
    """
    object_key = asset_service.generate_object_key(
        category=payload.category,
        entity_id=payload.entity_id,
        filename=payload.filename,
    )

    upload_url = asset_service.generate_upload_url(
        object_key=object_key,
        content_type=payload.content_type,
        expires=timedelta(minutes=10),
    )

    asset_url = asset_service.build_asset_url(object_key)

    return ApiResponse(
        data=UploadUrlResponseData(
            object_key=object_key,
            upload_url=upload_url,
            asset_url=asset_url,
        )
    )


@app.get("/assets", response_model=ApiResponse[AssetListResponseData])
def list_assets(
    limit: int = 20,
    category: str | None = None,
    entity_id: str | None = None,
    asset_service: AssetService = Depends(get_asset_service),
):
    try:
        rows = asset_service.list_assets(
            limit=limit,
            category=category,
            entity_id=entity_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    items = [AssetListItemData(**row) for row in rows]
    return ApiResponse(data=AssetListResponseData(items=items))


@app.post("/assets/complete-upload", response_model=ApiResponse[CompleteUploadResponseData])
def complete_upload(
    payload: CompleteUploadRequest,
    asset_service: AssetService = Depends(get_asset_service),
):
    """
    前端上传成功后通知后端确认。
    """
    try:
        asset_service.complete_upload(
            object_key=payload.object_key,
            category=payload.category,
            entity_id=payload.entity_id,
            filename=payload.filename,
            content_type=payload.content_type,
            file_size=payload.file_size,
            etag=payload.etag,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    asset_url = asset_service.build_asset_url(payload.object_key)

    return ApiResponse(
        data=CompleteUploadResponseData(
            object_key=payload.object_key,
            asset_url=asset_url,
            status="acknowledged",
        )
    )


@app.post("/tasks", response_model=ApiResponse[TaskData])
def create_task(
    payload: CreateTaskRequest,
    task_service: TaskService = Depends(get_task_service),
):
    try:
        task = task_service.create_task(
            object_key=payload.object_key,
            language=payload.language,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ApiResponse(data=task)


@app.get("/tasks", response_model=ApiResponse[TaskListResponseData])
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


@app.get("/tasks/{task_id}", response_model=ApiResponse[TaskData])
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


@app.post("/tasks/{task_id}/refresh", response_model=ApiResponse[TaskData])
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


@app.get("/tasks/{task_id}/transcript", response_model=ApiResponse[TaskTranscriptData])
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
