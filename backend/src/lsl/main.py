from fastapi import FastAPI
from datetime import timedelta

from lsl.config import Settings
from lsl.asset import AssetService
from lsl.asset.factory import create_storage_provider

app = FastAPI(title="LSL")

_env_settings = Settings.from_env()
settings = Settings(
    STORAGE_PROVIDER=_env_settings.STORAGE_PROVIDER or "oss",
    ASSET_BASE_URL=_env_settings.ASSET_BASE_URL,
    OSS_REGION=_env_settings.OSS_REGION,
    OSS_BUCKET=_env_settings.OSS_BUCKET,
    OSS_ACCESS_KEY_ID=_env_settings.OSS_ACCESS_KEY_ID,
    OSS_ACCESS_KEY_SECRET=_env_settings.OSS_ACCESS_KEY_SECRET,
)

storage = create_storage_provider(settings)

asset_service = AssetService(
    settings=settings,
    storage=storage,
)

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/assets/upload-url")
def generate_upload_url(
    category: str,
    entity_id: str,
    filename: str,
    content_type: str,
):
    """
    生成上传用 Presigned URL
    """
    object_key = asset_service.generate_object_key(
        category=category,
        entity_id=entity_id,
        filename=filename,
    )

    upload_url = asset_service.generate_upload_url(
        object_key=object_key,
        content_type=content_type,
        expires=timedelta(minutes=10),
    )

    asset_url = asset_service.build_asset_url(object_key)

    return {
        "object_key": object_key,
        "upload_url": upload_url,
        "asset_url": asset_url,
    }
