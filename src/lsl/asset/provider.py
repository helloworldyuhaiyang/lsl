from datetime import timedelta
from typing import Protocol

class StorageProvider(Protocol):
    """
    抽象存储接口：
    - 业务层只依赖这个接口
    - OSS / S3 / GCS 各自实现
    """

    def generate_presigned_put_url(
        self, 
        object_key: str,
        content_type: str,
        expires: timedelta,
        ) -> str:
        """
        生成上传用 Presigned URL(PUT)
        """
        ...

    def generate_presigned_get_url(
            self,
            object_key: str,
            expires: timedelta,
                ) -> str:
        """
        可选：私有读场景才需要
        默认不实现
        """
        ...

