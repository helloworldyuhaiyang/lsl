import uuid
from datetime import timedelta
from pathlib import Path

from lsl.config import Settings
from lsl.asset.provider import StorageProvider


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
    ):
        self._settings = settings
        self._storage = storage

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
