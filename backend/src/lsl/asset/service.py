import uuid
from datetime import timedelta
from pathlib import Path
from typing import Optional

from lsl.config import Settings
from lsl.asset.provider import StorageProvider
from lsl.asset.repository import AssetRepository


class AssetService:
    """
    asset 业务层：
    - 生成 object_key
    - 生成上传用 presigned URL
    - 生成访问 URL
    """

    def __init__(
        self,
        settings: Settings,
        storage: StorageProvider,
        repository: Optional[AssetRepository] = None,
    ):
        self._settings = settings
        self._storage = storage
        self._repository = repository

    def generate_object_key(
        self,
        *,
        category: str,
        entity_id: str,
        filename: str,
    ) -> str:
        """
        根据业务生成系统内部 asset 唯一标识(object key)
        """
        ext = Path(filename).suffix
        uid = uuid.uuid4().hex

        return f"{category}/{entity_id}/{uid}{ext}"


    def generate_upload_url(
        self,
        *,
        object_key: str,
        content_type: str,
        expires: timedelta = timedelta(minutes=10),
    ) -> str:
        """
        生成上传用 Presigned PUT URL
        """
        return self._storage.generate_presigned_put_url(
            object_key=object_key,
            content_type=content_type,
            expires=expires,
        )

    def build_asset_url(self, object_key: str) -> str:
        """
        生成最终访问 URL(读)
        """
        base = self._settings.ASSET_BASE_URL.rstrip("/")
        return f"{base}/{object_key}"

    def complete_upload(
        self,
        *,
        object_key: str,
        category: Optional[str],
        entity_id: Optional[str],
        filename: Optional[str],
        content_type: Optional[str],
        file_size: Optional[int],
        etag: Optional[str],
    ) -> None:
        if self._repository is None:
            raise RuntimeError("Asset repository is not configured. Set DATABASE_URL to enable persistence.")

        parsed_category, parsed_entity_id = self._parse_category_and_entity(object_key)

        final_category = category or parsed_category
        final_entity_id = entity_id or parsed_entity_id

        if category and category != parsed_category:
            raise ValueError("category does not match object_key")
        if entity_id and entity_id != parsed_entity_id:
            raise ValueError("entity_id does not match object_key")

        final_filename = filename or Path(object_key).name

        self._repository.upsert_completed_upload(
            object_key=object_key,
            category=final_category,
            entity_id=final_entity_id,
            filename=final_filename,
            content_type=content_type,
            file_size=file_size,
            etag=etag,
            storage_provider=self._settings.STORAGE_PROVIDER,
            upload_status=0,
        )

    @staticmethod
    def _parse_category_and_entity(object_key: str) -> tuple[str, str]:
        parts = [p for p in object_key.strip("/").split("/") if p]
        if len(parts) < 3:
            raise ValueError("object_key must be in format: {category}/{entity_id}/{filename}")
        return parts[0], parts[1]
