from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    # 存储相关（后面会逐步填）
    STORAGE_PROVIDER: str = "oss"
    ASSET_BASE_URL: str = ""

    # OSS
    OSS_REGION: str = "cn-hangzhou"
    OSS_BUCKET: str = "other"
    OSS_ACCESS_KEY_ID: str = "LTAI5tMcq8xHNYeMxA8JNqLF"
    OSS_ACCESS_KEY_SECRET: str = ""
