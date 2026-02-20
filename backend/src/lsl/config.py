import os
from dataclasses import dataclass


def _get_env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got: {raw!r}") from exc


def _get_env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number, got: {raw!r}") from exc


@dataclass(frozen=True)
class Settings:
    # 存储相关
    STORAGE_PROVIDER: str = ""
    ASSET_BASE_URL: str = ""
    DATABASE_URL: str = ""
    DB_POOL_MIN_SIZE: int = 1
    DB_POOL_MAX_SIZE: int = 10
    DB_POOL_TIMEOUT: float = 30.0

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
        database_url = os.getenv("DATABASE_URL", cls.DATABASE_URL).strip()
        db_pool_min_size = _get_env_int("DB_POOL_MIN_SIZE", cls.DB_POOL_MIN_SIZE)
        db_pool_max_size = _get_env_int("DB_POOL_MAX_SIZE", cls.DB_POOL_MAX_SIZE)
        db_pool_timeout = _get_env_float("DB_POOL_TIMEOUT", cls.DB_POOL_TIMEOUT)

        if db_pool_min_size <= 0:
            raise ValueError("DB_POOL_MIN_SIZE must be greater than 0")
        if db_pool_max_size < db_pool_min_size:
            raise ValueError("DB_POOL_MAX_SIZE must be greater than or equal to DB_POOL_MIN_SIZE")
        if db_pool_timeout <= 0:
            raise ValueError("DB_POOL_TIMEOUT must be greater than 0")
    
        return cls(
            STORAGE_PROVIDER=provider,
            ASSET_BASE_URL=asset_base_url,
            DATABASE_URL=database_url,
            DB_POOL_MIN_SIZE=db_pool_min_size,
            DB_POOL_MAX_SIZE=db_pool_max_size,
            DB_POOL_TIMEOUT=db_pool_timeout,
            OSS_REGION=region,
            OSS_BUCKET=bucket,
            OSS_ACCESS_KEY_ID=os.getenv("OSS_ACCESS_KEY_ID", cls.OSS_ACCESS_KEY_ID).strip(),
            OSS_ACCESS_KEY_SECRET=os.getenv("OSS_ACCESS_KEY_SECRET", cls.OSS_ACCESS_KEY_SECRET).strip(),
        )
