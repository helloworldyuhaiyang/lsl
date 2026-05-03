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


def _get_env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean, got: {raw!r}")


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
    ASSET_PUT_TIMEOUT: float = 120.0
    DATABASE_URL: str = "sqlite:///./data/lsl.sqlite3"
    DB_POOL_MIN_SIZE: int = 1
    DB_POOL_MAX_SIZE: int = 10
    DB_POOL_TIMEOUT: float = 30.0
    JOB_RUNNER_ENABLED: bool = True
    JOB_RUNNER_INTERVAL_SECONDS: float = 2.0
    JOB_RUNNER_BATCH_SIZE: int = 10
    JOB_RUNNER_MAX_WORKERS: int = 4

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

    # AI Script / LLM
    SCRIPT_PROVIDER: str = "llm"
    SCRIPT_LLM_API_KEY: str = ""
    SCRIPT_LLM_BASE_URL: str = "https://ark.cn-beijing.volces.com/api/v3"
    SCRIPT_LLM_MODEL: str = "doubao-1-5-pro-32k-250115"
    SCRIPT_LLM_HTTP_TIMEOUT: float = 60.0

    # TTS
    TTS_PROVIDER: str = "fake"
    TTS_REDIS_URL: str = "redis://127.0.0.1:6379/0"
    TTS_CACHE_TTL_SECONDS: int = 7200
    TTS_VOLC_APP_ID: str = ""
    TTS_VOLC_ACCESS_KEY: str = ""
    TTS_VOLC_RESOURCE_ID: str = "seed-tts-2.0"
    TTS_VOLC_URL: str = "https://openspeech.bytedance.com/api/v3/tts/unidirectional"
    TTS_VOLC_HTTP_TIMEOUT: float = 60.0
    TTS_DEFAULT_FORMAT: str = "mp3"
    TTS_DEFAULT_EMOTION_SCALE: float = 4.0
    TTS_DEFAULT_SPEECH_RATE: float = 0.0
    TTS_DEFAULT_LOUDNESS_RATE: float = 0.0

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
        job_runner_enabled = _get_env_bool("JOB_RUNNER_ENABLED", cls.JOB_RUNNER_ENABLED)
        job_runner_interval_seconds = _get_env_float(
            "JOB_RUNNER_INTERVAL_SECONDS",
            cls.JOB_RUNNER_INTERVAL_SECONDS,
        )
        job_runner_batch_size = _get_env_int("JOB_RUNNER_BATCH_SIZE", cls.JOB_RUNNER_BATCH_SIZE)
        job_runner_max_workers = _get_env_int("JOB_RUNNER_MAX_WORKERS", cls.JOB_RUNNER_MAX_WORKERS)
        volc_http_timeout = _get_env_float("VOLC_HTTP_TIMEOUT", cls.VOLC_HTTP_TIMEOUT)
        revision_llm_http_timeout = _get_env_float(
            "REVISION_LLM_HTTP_TIMEOUT",
            cls.REVISION_LLM_HTTP_TIMEOUT,
        )
        script_llm_http_timeout = _get_env_float(
            "SCRIPT_LLM_HTTP_TIMEOUT",
            cls.SCRIPT_LLM_HTTP_TIMEOUT,
        )
        tts_cache_ttl_seconds = _get_env_int("TTS_CACHE_TTL_SECONDS", cls.TTS_CACHE_TTL_SECONDS)
        tts_volc_http_timeout = _get_env_float("TTS_VOLC_HTTP_TIMEOUT", cls.TTS_VOLC_HTTP_TIMEOUT)
        tts_default_emotion_scale = _get_env_float("TTS_DEFAULT_EMOTION_SCALE", cls.TTS_DEFAULT_EMOTION_SCALE)
        tts_default_speech_rate = _get_env_float("TTS_DEFAULT_SPEECH_RATE", cls.TTS_DEFAULT_SPEECH_RATE)
        tts_default_loudness_rate = _get_env_float("TTS_DEFAULT_LOUDNESS_RATE", cls.TTS_DEFAULT_LOUDNESS_RATE)

        if db_pool_min_size <= 0:
            raise ValueError("DB_POOL_MIN_SIZE must be greater than 0")
        if db_pool_max_size < db_pool_min_size:
            raise ValueError("DB_POOL_MAX_SIZE must be greater than or equal to DB_POOL_MIN_SIZE")
        if db_pool_timeout <= 0:
            raise ValueError("DB_POOL_TIMEOUT must be greater than 0")
        if job_runner_interval_seconds <= 0:
            raise ValueError("JOB_RUNNER_INTERVAL_SECONDS must be greater than 0")
        if job_runner_batch_size <= 0:
            raise ValueError("JOB_RUNNER_BATCH_SIZE must be greater than 0")
        if job_runner_max_workers <= 0:
            raise ValueError("JOB_RUNNER_MAX_WORKERS must be greater than 0")
        if volc_http_timeout <= 0:
            raise ValueError("VOLC_HTTP_TIMEOUT must be greater than 0")
        if revision_llm_http_timeout <= 0:
            raise ValueError("REVISION_LLM_HTTP_TIMEOUT must be greater than 0")
        if script_llm_http_timeout <= 0:
            raise ValueError("SCRIPT_LLM_HTTP_TIMEOUT must be greater than 0")
        if tts_cache_ttl_seconds <= 0:
            raise ValueError("TTS_CACHE_TTL_SECONDS must be greater than 0")
        if tts_volc_http_timeout <= 0:
            raise ValueError("TTS_VOLC_HTTP_TIMEOUT must be greater than 0")
        if not 1 <= tts_default_emotion_scale <= 5:
            raise ValueError("TTS_DEFAULT_EMOTION_SCALE must be between 1 and 5")
        if not -50 <= tts_default_speech_rate <= 100:
            raise ValueError("TTS_DEFAULT_SPEECH_RATE must be between -50 and 100")
        if not -50 <= tts_default_loudness_rate <= 100:
            raise ValueError("TTS_DEFAULT_LOUDNESS_RATE must be between -50 and 100")
        
        tts_volc_app_id = _get_env_str("TTS_VOLC_APP_ID", cls.TTS_VOLC_APP_ID)
        tts_volc_access_key = _get_env_str("TTS_VOLC_ACCESS_KEY", cls.TTS_VOLC_ACCESS_KEY)
        tts_provider = os.getenv("TTS_PROVIDER", cls.TTS_PROVIDER).strip().lower() or cls.TTS_PROVIDER
        revision_provider = os.getenv("REVISION_PROVIDER", cls.REVISION_PROVIDER).strip().lower() or cls.REVISION_PROVIDER
        revision_llm_api_key = _get_env_str("REVISION_LLM_API_KEY", cls.REVISION_LLM_API_KEY)
        revision_llm_base_url = _get_env_str("REVISION_LLM_BASE_URL", cls.REVISION_LLM_BASE_URL)
        revision_llm_model = _get_env_str("REVISION_LLM_MODEL", cls.REVISION_LLM_MODEL)
        script_provider_default = "llm" if revision_provider == "llm" else cls.SCRIPT_PROVIDER
        script_provider = os.getenv("SCRIPT_PROVIDER", script_provider_default).strip().lower() or script_provider_default
        script_llm_api_key = _get_env_str("SCRIPT_LLM_API_KEY", revision_llm_api_key or cls.SCRIPT_LLM_API_KEY)
        script_llm_base_url = _get_env_str("SCRIPT_LLM_BASE_URL", revision_llm_base_url or cls.SCRIPT_LLM_BASE_URL)
        script_llm_model = _get_env_str("SCRIPT_LLM_MODEL", revision_llm_model or cls.SCRIPT_LLM_MODEL)

        return cls(
            STORAGE_PROVIDER=provider,
            ASSET_BASE_URL=asset_base_url,
            DATABASE_URL=database_url,
            DB_POOL_MIN_SIZE=db_pool_min_size,
            DB_POOL_MAX_SIZE=db_pool_max_size,
            DB_POOL_TIMEOUT=db_pool_timeout,
            JOB_RUNNER_ENABLED=job_runner_enabled,
            JOB_RUNNER_INTERVAL_SECONDS=job_runner_interval_seconds,
            JOB_RUNNER_BATCH_SIZE=job_runner_batch_size,
            JOB_RUNNER_MAX_WORKERS=job_runner_max_workers,
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
            REVISION_PROVIDER=revision_provider,
            REVISION_LLM_API_KEY=revision_llm_api_key,
            REVISION_LLM_BASE_URL=revision_llm_base_url,
            REVISION_LLM_MODEL=revision_llm_model,
            REVISION_LLM_HTTP_TIMEOUT=revision_llm_http_timeout,
            REVISION_LLM_DEBUG_FILE=_get_env_str("REVISION_LLM_DEBUG_FILE", cls.REVISION_LLM_DEBUG_FILE),
            SCRIPT_PROVIDER=script_provider,
            SCRIPT_LLM_API_KEY=script_llm_api_key,
            SCRIPT_LLM_BASE_URL=script_llm_base_url,
            SCRIPT_LLM_MODEL=script_llm_model,
            SCRIPT_LLM_HTTP_TIMEOUT=script_llm_http_timeout,
            TTS_PROVIDER=tts_provider,
            TTS_REDIS_URL=_get_env_str("TTS_REDIS_URL", cls.TTS_REDIS_URL),
            TTS_CACHE_TTL_SECONDS=tts_cache_ttl_seconds,
            TTS_VOLC_APP_ID=tts_volc_app_id,
            TTS_VOLC_ACCESS_KEY=tts_volc_access_key,
            TTS_VOLC_RESOURCE_ID=_get_env_str("TTS_VOLC_RESOURCE_ID", cls.TTS_VOLC_RESOURCE_ID),
            TTS_VOLC_URL=_get_env_str("TTS_VOLC_URL", cls.TTS_VOLC_URL),
            TTS_VOLC_HTTP_TIMEOUT=tts_volc_http_timeout,
            TTS_DEFAULT_FORMAT=_get_env_str("TTS_DEFAULT_FORMAT", cls.TTS_DEFAULT_FORMAT).lower(),
            TTS_DEFAULT_EMOTION_SCALE=tts_default_emotion_scale,
            TTS_DEFAULT_SPEECH_RATE=tts_default_speech_rate,
            TTS_DEFAULT_LOUDNESS_RATE=tts_default_loudness_rate,
        )
