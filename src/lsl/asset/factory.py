from lsl.config import Settings
from lsl.asset.provider import StorageProvider
from lsl.asset.fake_provider import FakeStorageProvider
from lsl.asset.oss_provider import OSSStorageProvider

def create_storage_provider(settings: Settings) -> StorageProvider:
    """
    根据配置创建 StorageProvider
    """
    if settings.STORAGE_PROVIDER == "fake":
        return FakeStorageProvider()

    # 后续扩展：
    if settings.STORAGE_PROVIDER == "oss":
        return OSSStorageProvider(settings)
    # if settings.STORAGE_PROVIDER == "s3":
    #     return S3StorageProvider(...)

    raise ValueError(
        f"Unsupported STORAGE_PROVIDER: {settings.STORAGE_PROVIDER}"
    )
