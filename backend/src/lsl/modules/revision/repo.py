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
        preserve_existing_drafts: bool = True,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> UtterancesRevisionModel:
        normalized_session_id = self._require_uuid(session_id, field_name="session_id")
        normalized_task_id = self._require_uuid(task_id, field_name="task_id")
        overlapping_source_seqs = self._find_overlapping_source_seqs(items)
        if overlapping_source_seqs:
            joined = ", ".join(str(seq) for seq in overlapping_source_seqs)
            raise RuntimeError(f"Overlapping source_seqs in revision items: {joined}")
        self._validate_generated_items(items)

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

                model.task_id = normalized_task_id
                model.user_prompt = user_prompt
                model.status = int(status)
                model.error_code = error_code
                model.error_message = error_message
                model.item_count = len(items)

                existing_items_by_span = {
                    (
                        int(existing_item.source_seq_start),
                        int(existing_item.source_seq_end),
                    ): existing_item
                    for existing_item in model.items
                }
                incoming_spans = {
                    (
                        int(item.source_seq_start),
                        int(item.source_seq_end),
                    )
                    for item in items
                }
                for existing_span, existing_item in list(existing_items_by_span.items()):
                    if existing_span not in incoming_spans:
                        model.items.remove(existing_item)

                for item in items:
                    span_key = (
                        int(item.source_seq_start),
                        int(item.source_seq_end),
                    )
                    model_item = existing_items_by_span.get(span_key)
                    if model_item is None:
                        model_item = UtterancesRevisionItemModel(
                            item_id=str(uuid.uuid4()),
                            task_id=self._require_uuid(item.task_id, field_name="task_id"),
                            source_seq_start=int(item.source_seq_start),
                            source_seq_end=int(item.source_seq_end),
                            source_seq_count=int(item.source_seq_count),
                            source_seqs=[int(seq) for seq in item.source_seqs],
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
                        model.items.append(model_item)
                        continue

                    model_item.task_id = self._require_uuid(item.task_id, field_name="task_id")
                    model_item.source_seq_start = int(item.source_seq_start)
                    model_item.source_seq_end = int(item.source_seq_end)
                    model_item.source_seq_count = int(item.source_seq_count)
                    model_item.source_seqs = [int(seq) for seq in item.source_seqs]
                    model_item.speaker = item.speaker
                    model_item.start_time = int(item.start_time)
                    model_item.end_time = int(item.end_time)
                    model_item.original_text = item.original_text
                    model_item.suggested_text = item.suggested_text
                    model_item.suggested_cue = item.suggested_cue
                    if preserve_existing_drafts:
                        if item.draft_text is not None:
                            model_item.draft_text = item.draft_text
                        if item.draft_cue is not None:
                            model_item.draft_cue = item.draft_cue
                    else:
                        model_item.draft_text = item.draft_text
                        model_item.draft_cue = item.draft_cue
                    model_item.score = int(item.score)
                    model_item.issue_tags = item.issue_tags
                    model_item.explanations = item.explanations

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
    def _find_overlapping_source_seqs(items: list[GeneratedRevisionItem]) -> list[int]:
        seen: set[int] = set()
        duplicates: set[int] = set()
        for item in items:
            for seq in item.source_seqs:
                normalized_seq = int(seq)
                if normalized_seq in seen:
                    duplicates.add(normalized_seq)
                    continue
                seen.add(normalized_seq)
        return sorted(duplicates)

    @staticmethod
    def _validate_generated_items(items: list[GeneratedRevisionItem]) -> None:
        for item in items:
            source_seqs = [int(seq) for seq in item.source_seqs]
            if not source_seqs:
                raise RuntimeError("Revision item source_seqs cannot be empty")

            ordered_source_seqs = sorted(source_seqs)
            expected_source_seqs = list(range(ordered_source_seqs[0], ordered_source_seqs[-1] + 1))
            if ordered_source_seqs != expected_source_seqs:
                raise RuntimeError(f"Revision item source_seqs must be contiguous: {ordered_source_seqs}")

            if int(item.source_seq_start) != ordered_source_seqs[0]:
                raise RuntimeError("Revision item source_seq_start does not match source_seqs")
            if int(item.source_seq_end) != ordered_source_seqs[-1]:
                raise RuntimeError("Revision item source_seq_end does not match source_seqs")
            if int(item.source_seq_count) != len(ordered_source_seqs):
                raise RuntimeError("Revision item source_seq_count does not match source_seqs")
