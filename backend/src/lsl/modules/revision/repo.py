from __future__ import annotations

import uuid
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session as OrmSession
from sqlalchemy.orm import selectinload, sessionmaker

from lsl.modules.revision.model import UtterancesRevisionItemModel, UtterancesRevisionModel
from lsl.modules.revision.types import GeneratedRevisionItem


class RevisionRepository:
    def __init__(self, session_factory: sessionmaker[OrmSession]) -> None:
        self._session_factory = session_factory

    @contextmanager
    def _session_scope(self) -> Iterator[OrmSession]:
        db = self._session_factory()
        try:
            yield db
        finally:
            db.close()

    def get_revision_by_session_id(self, session_id: str) -> UtterancesRevisionModel | None:
        normalized_session_id = self._parse_uuid_str(session_id)
        if normalized_session_id is None:
            return None

        stmt = (
            select(UtterancesRevisionModel)
            .options(selectinload(UtterancesRevisionModel.items))
            .where(UtterancesRevisionModel.session_id == normalized_session_id)
            .limit(1)
        )
        try:
            with self._session_scope() as db:
                return db.execute(stmt).scalar_one_or_none()
        except SQLAlchemyError as exc:  # pragma: no cover
            raise RuntimeError(f"Failed to query revision by session_id: {exc}") from exc

    def save_revision(
        self,
        *,
        session_id: str,
        task_id: str,
        user_prompt: str | None,
        status: int,
        items: list[GeneratedRevisionItem],
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> UtterancesRevisionModel:
        normalized_session_id = self._require_uuid(session_id, field_name="session_id")
        normalized_task_id = self._require_uuid(task_id, field_name="task_id")
        duplicate_seqs = self._find_duplicate_utterance_seqs(items)
        if duplicate_seqs:
            joined = ", ".join(str(seq) for seq in duplicate_seqs)
            raise RuntimeError(f"Duplicate utterance_seq in revision items: {joined}")

        try:
            with self._session_scope() as db:
                stmt = (
                    select(UtterancesRevisionModel)
                    .options(selectinload(UtterancesRevisionModel.items))
                    .where(UtterancesRevisionModel.session_id == normalized_session_id)
                    .limit(1)
                )
                model = db.execute(stmt).scalar_one_or_none()

                if model is None:
                    model = UtterancesRevisionModel(
                        revision_id=str(uuid.uuid4()),
                        session_id=normalized_session_id,
                        task_id=normalized_task_id,
                    )
                    db.add(model)
                else:
                    # Replace the whole item list for this revision in one pass.
                    model.items.clear()
                    db.flush()

                model.task_id = normalized_task_id
                model.user_prompt = user_prompt
                model.status = int(status)
                model.error_code = error_code
                model.error_message = error_message
                model.item_count = len(items)

                for item in items:
                    model.items.append(
                        UtterancesRevisionItemModel(
                            item_id=str(uuid.uuid4()),
                            task_id=self._require_uuid(item.task_id, field_name="task_id"),
                            utterance_seq=int(item.utterance_seq),
                            speaker=item.speaker,
                            start_time=int(item.start_time),
                            end_time=int(item.end_time),
                            original_text=item.original_text,
                            suggested_text=item.suggested_text,
                            suggested_cue=item.suggested_cue,
                            draft_text=item.draft_text,
                            draft_cue=item.draft_cue,
                            score=int(item.score),
                            issue_tags=item.issue_tags,
                            explanations=item.explanations,
                        )
                    )

                db.commit()
                db.refresh(model)
                _ = list(model.items)
                return model
        except SQLAlchemyError as exc:  # pragma: no cover
            raise RuntimeError(f"Failed to save revision: {exc}") from exc

    def update_revision_item(
        self,
        *,
        item_id: str,
        updates: dict[str, str | None],
    ) -> UtterancesRevisionItemModel | None:
        normalized_item_id = self._parse_uuid_str(item_id)
        if normalized_item_id is None:
            return None

        try:
            with self._session_scope() as db:
                model = db.get(UtterancesRevisionItemModel, normalized_item_id)
                if model is None:
                    return None

                for key, value in updates.items():
                    setattr(model, key, value)
                db.commit()
                db.refresh(model)
                return model
        except SQLAlchemyError as exc:  # pragma: no cover
            raise RuntimeError(f"Failed to update revision item: {exc}") from exc

    @staticmethod
    def _parse_uuid_str(value: str) -> str | None:
        try:
            return str(uuid.UUID(value))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _require_uuid(value: str, *, field_name: str) -> str:
        parsed = RevisionRepository._parse_uuid_str(value)
        if parsed is None:
            raise RuntimeError(f"Invalid {field_name}")
        return parsed

    @staticmethod
    def _find_duplicate_utterance_seqs(items: list[GeneratedRevisionItem]) -> list[int]:
        seen: set[int] = set()
        duplicates: set[int] = set()
        for item in items:
            seq = int(item.utterance_seq)
            if seq in seen:
                duplicates.add(seq)
                continue
            seen.add(seq)
        return sorted(duplicates)
