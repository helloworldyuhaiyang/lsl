from __future__ import annotations

from datetime import timedelta
import alibabacloud_oss_v2 as oss

from lsl.config import Settings


class OSSStorageProvider:
    def __init__(self, settings: Settings) -> None:
        cfg = oss.config.load_default()

        # 静态 AK（生产更推荐走 RAM Role / STS，但先按你当前需求来）
        cfg.credentials_provider = oss.credentials.StaticCredentialsProvider(
            settings.OSS_ACCESS_KEY_ID,
            settings.OSS_ACCESS_KEY_SECRET,
        )

        # v2 示例使用 region 来定位 endpoint
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
