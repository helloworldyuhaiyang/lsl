from __future__ import annotations

import uuid
from typing import Any

from lsl.modules.asset.service import AssetService
from lsl.modules.session.model import SessionModel
from lsl.modules.session.repo import SessionRepository
from lsl.modules.session.schema import (
    AssetSchema,
    CreateSessionRequest,
    SessionData,
    SessionSchema,
    TaskSchema,
    UpdateSessionRequest,
)
from lsl.modules.task.schema import TaskData
from lsl.modules.task.service import TaskService


class SessionService:
    def __init__(
        self,
        *,
        repository: SessionRepository,
        asset_service: AssetService,
        task_service: TaskService,
    ) -> None:
        self._repository = repository
        self._asset_service = asset_service
        self._task_service = task_service

    def create_session(self, payload: CreateSessionRequest) -> SessionData:
        session_id = str(uuid.uuid4())
        asset_object_key = self._normalize_object_key(payload.asset_object_key)
        current_task_id = payload.current_task_id

        self._validate_session_type(
            f_type=payload.f_type,
            asset_object_key=asset_object_key,
            current_task_id=current_task_id,
        )

        self._repository.create_session(
            session_id=session_id,
            title=payload.title,
            description=payload.description,
            language=payload.language,
            f_type=payload.f_type,
            asset_object_key=asset_object_key,
            current_task_id=current_task_id,
        )

        return self.get_session(session_id)

    def get_session(self, session_id: str) -> SessionData:
        session = self._repository.get_session_by_id(session_id)
        if session is None:
            raise ValueError("session not found")

        asset: dict[str, Any] | None = None
        asset_object_key = self._normalize_object_key(session.asset_object_key)
        if asset_object_key is not None:
            try:
                asset = self._asset_service.get_asset_by_object_key(object_key=asset_object_key)
            except ValueError:
                asset = None

        task: TaskData | None = None
        if session.current_task_id is not None:
            try:
                task = self._task_service.get_task(task_id=session.current_task_id, auto_refresh=False)
            except ValueError:
                task = None

        return self._to_session_data(session, asset=asset, task=task)

    def list_sessions(
        self,
        *,
        limit: int = 20,
        offset: int = 0,
        query: str | None = None,
        status: int | None = None,
    ) -> list[SessionData]:
        if limit <= 0:
            raise ValueError("limit must be greater than 0")
        if limit > 100:
            raise ValueError("limit must be less than or equal to 100")
        if offset < 0:
            raise ValueError("offset must be greater than or equal to 0")
        if status is not None and status not in (0, 1, 2, 3, 4):
            raise ValueError("status must be one of 0,1,2,3,4")

        sessions = self._repository.list_sessions(
            limit=limit,
            offset=offset,
            query=query,
        )

        assets = self._load_assets_by_sessions(sessions)
        tasks = self._load_tasks_by_sessions(sessions)

        items: list[SessionData] = []
        for session in sessions:
            task_id = session.current_task_id
            asset_object_key = self._normalize_object_key(session.asset_object_key)
            asset = assets.get(asset_object_key) if asset_object_key else None
            task = tasks.get(task_id) if task_id else None
            session_data = self._to_session_data(
                session,
                asset=asset,
                task=task,
            )
            items.append(session_data)

        return items

    def update_session(self, *, session_id: str, payload: UpdateSessionRequest) -> SessionData:
        existing = self._repository.get_session_by_id(session_id)
        if existing is None:
            raise ValueError("session not found")

        updates: dict[str, Any] = payload.model_dump(exclude_unset=True)

        if updates.get("title") is None and "title" in updates:
            raise ValueError("title cannot be null")
        if updates.get("f_type") is None and "f_type" in updates:
            raise ValueError("f_type cannot be null")

        if not updates:
            return self.get_session(session_id)

        final_asset_object_key = self._normalize_object_key(
            updates.get("asset_object_key", existing.asset_object_key)
        )
        final_task_id_raw = updates.get("current_task_id")
        if final_task_id_raw is None and "current_task_id" in updates:
            final_task_id = None
        else:
            final_task_id = final_task_id_raw if final_task_id_raw is not None else existing.current_task_id
        final_f_type = int(updates["f_type"]) if "f_type" in updates else int(existing.f_type)

        self._validate_session_type(
            f_type=final_f_type,
            asset_object_key=final_asset_object_key,
            current_task_id=final_task_id,
        )

        self._repository.update_session(session_id=session_id, updates=updates)
        return self.get_session(session_id)

    def _to_session_data(
        self,
        session: SessionModel,
        *,
        asset: dict[str, Any] | None = None,
        task: TaskData | None = None,
    ) -> SessionData:
        return SessionData.model_validate(
            {
                "session": SessionSchema.model_validate(session),
                "asset": AssetSchema.model_validate(asset) if asset is not None else None,
                "task": TaskSchema.model_validate(task) if task is not None else None,
            }
        )

    def _load_assets_by_sessions(self, sessions: list[SessionModel]) -> dict[str, dict[str, Any]]:
        object_keys_set: set[str] = set()
        for session in sessions:
            normalized = self._normalize_object_key(session.asset_object_key)
            if normalized is not None:
                object_keys_set.add(normalized)

        if not object_keys_set:
            return {}
        return self._asset_service.list_assets_by_object_keys(object_keys=sorted(object_keys_set))

    def _load_tasks_by_sessions(self, sessions: list[SessionModel]) -> dict[str, TaskData]:
        task_ids = sorted(
            {
                session.current_task_id
                for session in sessions
                if session.current_task_id is not None
            }
        )
        if not task_ids:
            return {}
        return self._task_service.list_tasks_by_ids(task_ids=task_ids, auto_refresh=False)

    @staticmethod
    def _normalize_object_key(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lstrip("/")
        return normalized or None

    @staticmethod
    def _validate_session_type(
        *,
        f_type: int,
        asset_object_key: str | None,
        current_task_id: str | None,
    ) -> None:
        if f_type not in (1, 2):
            raise ValueError("f_type must be one of 1(recording) or 2(text)")

        if f_type == 1 and not asset_object_key and not current_task_id:
            raise ValueError("recording session requires asset_object_key or current_task_id")
