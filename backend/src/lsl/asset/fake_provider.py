from datetime import timedelta
from urllib.parse import urlencode


class FakeStorageProvider:
    """
    用于本地开发 / 测试的 Fake Provider
    不做真实签名，只返回可读 URL
    """

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
        """
        可选：私有读场景才需要
        默认不实现
        """
        ...