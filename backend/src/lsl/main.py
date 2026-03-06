from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, cast

from fastapi import Depends, FastAPI, HTTPException, Request
from datetime import timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

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
from lsl.session import SessionRepository, SessionService
from lsl.session.schemas import (
    CreateSessionRequest,
    SessionData,
    SessionListResponseData,
    UpdateSessionRequest,
)
from lsl.task import TaskRepository, TaskService
from lsl.task.schemas import (
    CreateTaskRequest,
    TaskData,
    TaskListResponseData,
    TaskTranscriptData,
)

if TYPE_CHECKING:
    from psycopg_pool import ConnectionPool
    from sqlalchemy.engine import Engine

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


def _to_sqlalchemy_database_url(database_url: str) -> str:
    if database_url.startswith("postgresql+"):
        return database_url
    if database_url.startswith("postgresql://"):
        return "postgresql+psycopg://" + database_url[len("postgresql://") :]
    return database_url


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool: ConnectionPool | None = None
    session_engine: Engine | None = None
    asset_repository: AssetRepository | None = None
    task_repository: TaskRepository | None = None
    session_repository: SessionRepository | None = None

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
        session_engine = create_engine(
            _to_sqlalchemy_database_url(settings.DATABASE_URL),
            pool_pre_ping=True,
        )
        session_factory = sessionmaker(bind=session_engine, autoflush=False, expire_on_commit=False)
        session_repository = SessionRepository(session_factory)

    app.state.asset_service = AssetService(
        settings=settings,
        storage=storage,
        repository=asset_repository,
    )
    app.state.task_service = (
        TaskService(
            repository=task_repository,
            asr_provider=asr_provider,
        )
        if task_repository is not None
        else None
    )
    app.state.session_service = (
        SessionService(
            repository=session_repository,
            asset_service=app.state.asset_service,
            task_service=app.state.task_service,
        )
        if session_repository is not None and app.state.task_service is not None
        else None
    )
    app.state.db_pool = pool

    try:
        yield
    finally:
        if pool is not None:
            pool.close()
        if session_engine is not None:
            session_engine.dispose()


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


def get_session_service(request: Request) -> SessionService:
    service = getattr(request.app.state, "session_service", None)
    if service is None:
        raise HTTPException(status_code=500, detail="Session service is not initialized")
    return cast(SessionService, service)


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
            audio_url=payload.audio_url,
            language=payload.language,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ApiResponse(data=task)


@app.post("/sessions", response_model=ApiResponse[SessionData])
def create_session(
    payload: CreateSessionRequest,
    session_service: SessionService = Depends(get_session_service),
):
    try:
        session = session_service.create_session(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ApiResponse(data=session)


@app.get("/sessions", response_model=ApiResponse[SessionListResponseData])
def list_sessions(
    limit: int = 20,
    offset: int = 0,
    query: str | None = None,
    status: int | None = None,
    session_service: SessionService = Depends(get_session_service),
):
    try:
        items = session_service.list_sessions(
            limit=limit,
            offset=offset,
            query=query,
            status=status,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ApiResponse(data=SessionListResponseData(items=items))


@app.get("/sessions/{session_id}", response_model=ApiResponse[SessionData])
def get_session(
    session_id: str,
    session_service: SessionService = Depends(get_session_service),
):
    try:
        session = session_service.get_session(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ApiResponse(data=session)


@app.patch("/sessions/{session_id}", response_model=ApiResponse[SessionData])
def update_session(
    session_id: str,
    payload: UpdateSessionRequest,
    session_service: SessionService = Depends(get_session_service),
):
    try:
        session = session_service.update_session(session_id=session_id, payload=payload)
    except ValueError as exc:
        detail = str(exc)
        status_code = 404 if detail == "session not found" else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ApiResponse(data=session)


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
