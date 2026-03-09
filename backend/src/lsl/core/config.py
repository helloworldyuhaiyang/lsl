import os
from dataclasses import dataclass

from dotenv import load_dotenv


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


def _get_env_str(name: str, default: str) -> str:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip()
    if value == "":
        return default
    return value


@dataclass(frozen=True)
class Settings:
    # 存储相关
    STORAGE_PROVIDER: str = ""
    ASSET_BASE_URL: str = ""
    DATABASE_URL: str = "postgresql://yuhaiyang:@127.0.0.1:5432/lsl"
    DB_POOL_MIN_SIZE: int = 1
    DB_POOL_MAX_SIZE: int = 10
    DB_POOL_TIMEOUT: float = 30.0

    # OSS
    OSS_REGION: str = "cn-hangzhou"
    OSS_BUCKET: str = ""
    OSS_ACCESS_KEY_ID: str = ""
    OSS_ACCESS_KEY_SECRET: str = ""

    # ASR
    ASR_PROVIDER: str = "noop"
    VOLC_APP_KEY: str = ""
    VOLC_ACCESS_KEY: str = ""
    VOLC_RESOURCE_ID: str = "volc.bigasr.auc"
    VOLC_SUBMIT_URL: str = "https://openspeech-direct.zijieapi.com/api/v3/auc/bigmodel/submit"
    VOLC_QUERY_URL: str = "https://openspeech-direct.zijieapi.com/api/v3/auc/bigmodel/query"
    VOLC_MODEL_NAME: str = "bigmodel"
    VOLC_UID: str = "lsl_user"
    VOLC_HTTP_TIMEOUT: float = 15.0

    # Revision / LLM
    REVISION_PROVIDER: str = "fake"
    REVISION_LLM_API_KEY: str = ""
    REVISION_LLM_BASE_URL: str = "https://ark.cn-beijing.volces.com/api/v3"
    REVISION_LLM_MODEL: str = "doubao-1-5-pro-32k-250115"
    REVISION_LLM_HTTP_TIMEOUT: float = 60.0
    REVISION_LLM_DEBUG_FILE: str = ""

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv(override=False)

        provider = os.getenv("STORAGE_PROVIDER", cls.STORAGE_PROVIDER).strip().lower()
        region = os.getenv("OSS_REGION", cls.OSS_REGION).strip()
        bucket = os.getenv("OSS_BUCKET", cls.OSS_BUCKET).strip()

        asset_base_url = os.getenv("ASSET_BASE_URL", cls.ASSET_BASE_URL).strip().rstrip("/")
        database_url = _get_env_str("DATABASE_URL", cls.DATABASE_URL)
        db_pool_min_size = _get_env_int("DB_POOL_MIN_SIZE", cls.DB_POOL_MIN_SIZE)
        db_pool_max_size = _get_env_int("DB_POOL_MAX_SIZE", cls.DB_POOL_MAX_SIZE)
        db_pool_timeout = _get_env_float("DB_POOL_TIMEOUT", cls.DB_POOL_TIMEOUT)
        volc_http_timeout = _get_env_float("VOLC_HTTP_TIMEOUT", cls.VOLC_HTTP_TIMEOUT)
        revision_llm_http_timeout = _get_env_float(
            "REVISION_LLM_HTTP_TIMEOUT",
            cls.REVISION_LLM_HTTP_TIMEOUT,
        )

        if db_pool_min_size <= 0:
            raise ValueError("DB_POOL_MIN_SIZE must be greater than 0")
        if db_pool_max_size < db_pool_min_size:
            raise ValueError("DB_POOL_MAX_SIZE must be greater than or equal to DB_POOL_MIN_SIZE")
        if db_pool_timeout <= 0:
            raise ValueError("DB_POOL_TIMEOUT must be greater than 0")
        if volc_http_timeout <= 0:
            raise ValueError("VOLC_HTTP_TIMEOUT must be greater than 0")
        if revision_llm_http_timeout <= 0:
            raise ValueError("REVISION_LLM_HTTP_TIMEOUT must be greater than 0")
        
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
            ASR_PROVIDER=os.getenv("ASR_PROVIDER", cls.ASR_PROVIDER).strip().lower() or cls.ASR_PROVIDER,
            VOLC_APP_KEY=_get_env_str("VOLC_APP_KEY", cls.VOLC_APP_KEY),
            VOLC_ACCESS_KEY=_get_env_str("VOLC_ACCESS_KEY", cls.VOLC_ACCESS_KEY),
            VOLC_RESOURCE_ID=_get_env_str("VOLC_RESOURCE_ID", cls.VOLC_RESOURCE_ID),
            VOLC_SUBMIT_URL=_get_env_str("VOLC_SUBMIT_URL", cls.VOLC_SUBMIT_URL),
            VOLC_QUERY_URL=_get_env_str("VOLC_QUERY_URL", cls.VOLC_QUERY_URL),
            VOLC_MODEL_NAME=_get_env_str("VOLC_MODEL_NAME", cls.VOLC_MODEL_NAME),
            VOLC_UID=_get_env_str("VOLC_UID", cls.VOLC_UID),
            VOLC_HTTP_TIMEOUT=volc_http_timeout,
            REVISION_PROVIDER=os.getenv("REVISION_PROVIDER", cls.REVISION_PROVIDER).strip().lower() or cls.REVISION_PROVIDER,
            REVISION_LLM_API_KEY=_get_env_str("REVISION_LLM_API_KEY", cls.REVISION_LLM_API_KEY),
            REVISION_LLM_BASE_URL=_get_env_str("REVISION_LLM_BASE_URL", cls.REVISION_LLM_BASE_URL),
            REVISION_LLM_MODEL=_get_env_str("REVISION_LLM_MODEL", cls.REVISION_LLM_MODEL),
            REVISION_LLM_HTTP_TIMEOUT=revision_llm_http_timeout,
            REVISION_LLM_DEBUG_FILE=_get_env_str("REVISION_LLM_DEBUG_FILE", cls.REVISION_LLM_DEBUG_FILE),
        )
