from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Generic, TypeVar

from fastapi import FastAPI
from pydantic import BaseModel

from lsl.core import Settings, close_database_resources, configure_logging, create_database_resources
from lsl.modules.asset import AssetRepository, AssetService, create_storage_provider
from lsl.modules.asset.api import router as asset_router
from lsl.modules.revision import RevisionRepository, RevisionService, create_revision_generator
from lsl.modules.revision.api import router as revision_router
from lsl.modules.script import ScriptService, create_script_generator
from lsl.modules.script.api import router as script_router
from lsl.modules.session import SessionRepository, SessionService
from lsl.modules.session.api import router as session_router
from lsl.modules.task import TaskRepository, TaskService, create_asr_provider
from lsl.modules.task.api import router as task_router
from lsl.modules.tts import TtsCache, TtsRepository, TtsService, create_tts_provider
from lsl.modules.tts.api import router as tts_router

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    code: int = 0
    message: str = "successful"
    data: T


class HealthData(BaseModel):
    status: str


configure_logging()
settings = Settings.from_env()


@asynccontextmanager
async def lifespan(app: FastAPI):
    db_resources = create_database_resources(settings)

    asset_repository = (
        AssetRepository(db_resources.session_factory)
        if db_resources.session_factory is not None
        else None
    )
    task_repository = (
        TaskRepository(db_resources.session_factory)
        if db_resources.session_factory is not None
        else None
    )
    session_repository = (
        SessionRepository(db_resources.session_factory)
        if db_resources.session_factory is not None
        else None
    )
    revision_repository = (
        RevisionRepository(db_resources.session_factory)
        if db_resources.session_factory is not None
        else None
    )
    tts_repository = (
        TtsRepository(db_resources.session_factory)
        if db_resources.session_factory is not None
        else None
    )

    asset_service = AssetService(
        settings=settings,
        storage=create_storage_provider(settings),
        repository=asset_repository,
    )
    task_service = (
        TaskService(
            repository=task_repository,
            asr_provider=create_asr_provider(settings),
        )
        if task_repository is not None
        else None
    )
    session_service = (
        SessionService(
            repository=session_repository,
            asset_service=asset_service,
            task_service=task_service,
        )
        if session_repository is not None and task_service is not None
        else None
    )
    revision_service = (
        RevisionService(
            repository=revision_repository,
            generator=create_revision_generator(settings),
            session_service=session_service,
            task_service=task_service,
        )
        if revision_repository is not None and session_service is not None and task_service is not None
        else None
    )
    tts_service = (
        TtsService(
            repository=tts_repository,
            provider=create_tts_provider(settings),
            cache=TtsCache(
                redis_url=settings.TTS_REDIS_URL,
                ttl_seconds=settings.TTS_CACHE_TTL_SECONDS,
            ),
            session_service=session_service,
            revision_service=revision_service,
            asset_service=asset_service,
            settings=settings,
        )
        if tts_repository is not None and session_service is not None and revision_service is not None
        else None
    )
    script_service = (
        ScriptService(
            generator=create_script_generator(settings),
            session_service=session_service,
            task_service=task_service,
            revision_service=revision_service,
        )
        if session_service is not None and task_service is not None and revision_service is not None
        else None
    )

    app.state.settings = settings
    app.state.db_resources = db_resources
    app.state.asset_service = asset_service
    app.state.task_service = task_service
    app.state.session_service = session_service
    app.state.revision_service = revision_service
    app.state.tts_service = tts_service
    app.state.script_service = script_service

    try:
        yield
    finally:
        if tts_service is not None:
            tts_service.shutdown()
        if revision_service is not None:
            revision_service.shutdown()
        close_database_resources(db_resources)


app = FastAPI(title="LSL", lifespan=lifespan)
app.include_router(asset_router)
app.include_router(task_router)
app.include_router(session_router)
app.include_router(script_router)
app.include_router(revision_router)
app.include_router(tts_router)


@app.get("/health", response_model=ApiResponse[HealthData])
def health():
    return ApiResponse(data=HealthData(status="ok"))
