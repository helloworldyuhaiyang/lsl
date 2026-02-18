import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    # 存储相关
    STORAGE_PROVIDER: str = ""
    ASSET_BASE_URL: str = ""

    # OSS
    OSS_REGION: str = "cn-hangzhou"
    OSS_BUCKET: str = ""
    OSS_ACCESS_KEY_ID: str = ""
    OSS_ACCESS_KEY_SECRET: str = ""

    @classmethod
    def from_env(cls) -> "Settings":
        provider = os.getenv("STORAGE_PROVIDER", cls.STORAGE_PROVIDER).strip().lower()
        region = os.getenv("OSS_REGION", cls.OSS_REGION).strip()
        bucket = os.getenv("OSS_BUCKET", cls.OSS_BUCKET).strip()

        asset_base_url = os.getenv("ASSET_BASE_URL", cls.ASSET_BASE_URL).strip().rstrip("/")
    
        return cls(
            STORAGE_PROVIDER=provider,
            ASSET_BASE_URL=asset_base_url,
            OSS_REGION=region,
            OSS_BUCKET=bucket,
            OSS_ACCESS_KEY_ID=os.getenv("OSS_ACCESS_KEY_ID", cls.OSS_ACCESS_KEY_ID).strip(),
            OSS_ACCESS_KEY_SECRET=os.getenv("OSS_ACCESS_KEY_SECRET", cls.OSS_ACCESS_KEY_SECRET).strip(),
        )
