from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, cast

from fastapi import Depends, FastAPI, HTTPException, Request
from datetime import timedelta

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

if TYPE_CHECKING:
    from psycopg_pool import ConnectionPool

_env_settings = Settings.from_env()
settings = Settings(
    STORAGE_PROVIDER=_env_settings.STORAGE_PROVIDER or "oss",
    ASSET_BASE_URL=_env_settings.ASSET_BASE_URL,
    DATABASE_URL=_env_settings.DATABASE_URL,
    DB_POOL_MIN_SIZE=_env_settings.DB_POOL_MIN_SIZE,
    DB_POOL_MAX_SIZE=_env_settings.DB_POOL_MAX_SIZE,
    DB_POOL_TIMEOUT=_env_settings.DB_POOL_TIMEOUT,
    OSS_REGION=_env_settings.OSS_REGION,
    OSS_BUCKET=_env_settings.OSS_BUCKET,
    OSS_ACCESS_KEY_ID=_env_settings.OSS_ACCESS_KEY_ID,
    OSS_ACCESS_KEY_SECRET=_env_settings.OSS_ACCESS_KEY_SECRET,
)

storage = create_storage_provider(settings)


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool: ConnectionPool | None = None
    repository: AssetRepository | None = None

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
        repository = AssetRepository(pool)

    app.state.asset_service = AssetService(
        settings=settings,
        storage=storage,
        repository=repository,
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
    当前阶段：写入 assets 表并返回确认结果。
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
