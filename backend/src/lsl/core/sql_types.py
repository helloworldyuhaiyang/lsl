from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import String, Text
from sqlalchemy.types import TypeDecorator


class UUIDHexString(TypeDecorator[str]):
    impl = String(32)
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return value.hex

        normalized = str(value).strip()
        if not normalized:
            return None
        return uuid.UUID(normalized).hex

    def process_result_value(self, value: Any, dialect: Any) -> str | None:
        if value is None:
            return None
        return str(value)


class JSONString(TypeDecorator[Any]):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> str | None:
        if value is None:
            return None
        return json.dumps(value, ensure_ascii=False)

    def process_result_value(self, value: Any, dialect: Any) -> Any:
        if value is None or value == "":
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value

