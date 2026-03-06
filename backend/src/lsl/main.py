from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Generic, TypeVar

from fastapi import FastAPI
from pydantic import BaseModel

from lsl.core import Settings, close_database_resources, configure_logging, create_database_resources
from lsl.modules.asset import AssetRepository, AssetService, create_storage_provider
from lsl.modules.asset.api import router as asset_router
from lsl.modules.session import SessionRepository, SessionService
from lsl.modules.session.api import router as session_router
from lsl.modules.task import TaskRepository, TaskService, create_asr_provider
from lsl.modules.task.api import router as task_router

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

    asset_repository = AssetRepository(db_resources.pool) if db_resources.pool is not None else None
    task_repository = TaskRepository(db_resources.pool) if db_resources.pool is not None else None
    session_repository = (
        SessionRepository(db_resources.session_factory)
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

    app.state.settings = settings
    app.state.db_resources = db_resources
    app.state.asset_service = asset_service
    app.state.task_service = task_service
    app.state.session_service = session_service

    try:
        yield
    finally:
        close_database_resources(db_resources)


app = FastAPI(title="LSL", lifespan=lifespan)
app.include_router(asset_router)
app.include_router(task_router)
app.include_router(session_router)


@app.get("/health", response_model=ApiResponse[HealthData])
def health():
    return ApiResponse(data=HealthData(status="ok"))
