from __future__ import annotations

from datetime import timedelta
from urllib.parse import urlencode

import alibabacloud_oss_v2 as oss

from lsl.core.config import Settings
from lsl.modules.asset.types import StorageProvider


class FakeStorageProvider:
    def generate_presigned_put_url(
        self,
        object_key: str,
        content_type: str,
        expires: timedelta,
    ) -> str:
        params = urlencode(
            {
                "object_key": object_key,
                "content_type": content_type,
                "expires": int(expires.total_seconds()),
            }
        )
        return f"http://fake-storage/upload?{params}"

    def generate_presigned_get_url(
        self,
        object_key: str,
        expires: timedelta,
    ) -> str:
        return f"http://fake-storage/object/{object_key}?expires={int(expires.total_seconds())}"


class OSSStorageProvider:
    def __init__(self, settings: Settings) -> None:
        if not settings.OSS_BUCKET:
            raise ValueError("OSS_BUCKET is required when STORAGE_PROVIDER=oss")
        if not settings.OSS_ACCESS_KEY_ID:
            raise ValueError("OSS_ACCESS_KEY_ID is required when STORAGE_PROVIDER=oss")
        if not settings.OSS_ACCESS_KEY_SECRET:
            raise ValueError("OSS_ACCESS_KEY_SECRET is required when STORAGE_PROVIDER=oss")

        cfg = oss.config.load_default()
        cfg.credentials_provider = oss.credentials.StaticCredentialsProvider(
            settings.OSS_ACCESS_KEY_ID,
            settings.OSS_ACCESS_KEY_SECRET,
        )
        cfg.region = settings.OSS_REGION

        self._client = oss.Client(cfg)
        self._bucket = settings.OSS_BUCKET

    def generate_presigned_put_url(
        self,
        object_key: str,
        content_type: str,
        expires: timedelta,
    ) -> str:
        pre = self._client.presign(
            oss.PutObjectRequest(
                bucket=self._bucket,
                key=object_key,
                content_type=content_type,
            ),
            expires=expires,
        )
        return pre.url or ""

    def generate_presigned_get_url(
        self,
        object_key: str,
        expires: timedelta,
    ) -> str:
        pre = self._client.presign(
            oss.GetObjectRequest(
                bucket=self._bucket,
                key=object_key,
            ),
            expires=expires,
        )
        return pre.url or ""


def create_storage_provider(settings: Settings) -> StorageProvider:
    if settings.STORAGE_PROVIDER == "fake":
        return FakeStorageProvider()
    if settings.STORAGE_PROVIDER == "oss":
        return OSSStorageProvider(settings)
    raise ValueError(f"Unsupported STORAGE_PROVIDER: {settings.STORAGE_PROVIDER}")
