from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Protocol


@dataclass(frozen=True, slots=True)
class AssetLocation:
    category: str
    entity_id: str
    filename: str


class StorageProvider(Protocol):
    def generate_presigned_put_url(
        self,
        object_key: str,
        content_type: str,
        expires: timedelta,
    ) -> str:
        ...

    def generate_presigned_get_url(
        self,
        object_key: str,
        expires: timedelta,
    ) -> str:
        ...
