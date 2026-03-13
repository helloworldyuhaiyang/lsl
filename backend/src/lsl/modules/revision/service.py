from __future__ import annotations

import logging
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

from lsl.modules.revision.model import UtterancesRevisionItemModel, UtterancesRevisionModel
from lsl.modules.revision.repo import RevisionRepository
from lsl.modules.revision.schema import RevisionData, RevisionItemData, UpdateRevisionItemRequest
from lsl.modules.revision.types import (
    GeneratedRevisionItem,
    RevisionGenerateRequest,
    RevisionGenerator,
    RevisionPromptUtterance,
    RevisionStatus,
    RevisionSuggestion,
)
from lsl.modules.session.service import SessionService
from lsl.modules.task.schema import TaskTranscriptUtterance
from lsl.modules.task.service import TaskService

logger = logging.getLogger(__name__)

_REVISION_BACKGROUND_MAX_WORKERS = 2


class RevisionService:
    def __init__(
        self,
        *,
        repository: RevisionRepository,
        generator: RevisionGenerator,
        session_service: SessionService,
        task_service: TaskService,
    ) -> None:
        self._repository = repository
        self._generator = generator
        self._session_service = session_service
        self._task_service = task_service
        self._background_executor = ThreadPoolExecutor(
            max_workers=_REVISION_BACKGROUND_MAX_WORKERS,
            thread_name_prefix="revision-job",
        )
        self._job_tokens: dict[str, str] = {}
        self._job_tokens_lock = Lock()

    def shutdown(self) -> None:
        self._background_executor.shutdown(wait=False, cancel_futures=False)

    def get_revision(self, *, session_id: str) -> RevisionData:
        model = self._repository.get_revision_by_session_id(session_id)
        if model is None:
            raise ValueError("revision not found")
        return self._to_revision_data(model)

    def create_revision(
        self,
        *,
        session_id: str,
        user_prompt: str | None = None,
        force: bool = False,
    ) -> RevisionData:
        session_data = self._session_service.get_session(session_id)
        task_id = session_data.session.current_task_id
        if task_id is None:
            raise ValueError("session current_task_id is missing")

        existing = self._repository.get_revision_by_session_id(session_id)
        if (
            existing is not None
            and not force
            and str(existing.task_id) == task_id
            and (existing.user_prompt or None) == user_prompt
        ):
            if int(existing.status) == int(RevisionStatus.COMPLETED) and len(existing.items) > 0:
                return self._to_revision_data(existing)
            if int(existing.status) == int(RevisionStatus.GENERATING):
                return self._to_revision_data(existing)

        transcript = self._task_service.get_transcript(task_id=task_id, include_raw=False)
        initial_items = self._build_initial_revision_items(task_id=task_id, utterances=transcript.utterances)
        model = self._repository.save_revision(
            session_id=session_id,
            task_id=task_id,
            user_prompt=user_prompt,
            status=int(RevisionStatus.GENERATING),
            items=initial_items,
            preserve_existing_drafts=False,
            error_code=None,
            error_message=None,
        )

        job_token = self._register_job(session_id)
        try:
            self._background_executor.submit(
                self._run_revision_job,
                session_id,
                task_id,
                user_prompt,
                transcript.utterances,
                job_token,
            )
        except Exception as exc:
            self._clear_job(session_id=session_id, job_token=job_token)
            self._repository.save_revision(
                session_id=session_id,
                task_id=task_id,
                user_prompt=user_prompt,
                status=int(RevisionStatus.FAILED),
                items=initial_items,
                preserve_existing_drafts=False,
                error_code="revision_job_schedule_failed",
                error_message=str(exc),
            )
            raise RuntimeError(f"Failed to schedule revision job: {exc}") from exc

        return self._to_revision_data(model)

    def update_revision_item(self, *, item_id: str, payload: UpdateRevisionItemRequest) -> RevisionItemData:
        updates = payload.model_dump(exclude_unset=True)
        if not updates:
            raise ValueError("draft_text or draft_cue is required")

        item = self._repository.update_revision_item(item_id=item_id, updates=updates)
        if item is None:
            raise ValueError("revision item not found")
        return self._to_revision_item_data(item)

    def _run_revision_job(
        self,
        session_id: str,
        task_id: str,
        user_prompt: str | None,
        utterances: list[TaskTranscriptUtterance],
        job_token: str,
    ) -> None:
        current_items = self._build_initial_revision_items(task_id=task_id, utterances=utterances)
        prompt_utterances = self._build_prompt_utterances(utterances)
        utterance_by_seq = {int(item.seq): item for item in utterances}
        req = RevisionGenerateRequest(
            task_id=task_id,
            user_prompt=user_prompt,
            utterances=prompt_utterances,
        )

        try:
            for segment_suggestions in self._generator.generate_progressively(req):
                if not self._is_active_job(session_id=session_id, job_token=job_token):
                    logger.info("Revision job superseded session_id=%s task_id=%s", session_id, task_id)
                    return

                generated_segment_items = [
                    self._build_generated_revision_item(
                        task_id=task_id,
                        utterance_by_seq=utterance_by_seq,
                        suggestion=suggestion,
                    )
                    for suggestion in segment_suggestions
                ]
                current_items = self._merge_generated_items(
                    current_items=current_items,
                    incoming_items=generated_segment_items,
                )

                self._repository.save_revision(
                    session_id=session_id,
                    task_id=task_id,
                    user_prompt=user_prompt,
                    status=int(RevisionStatus.GENERATING),
                    items=current_items,
                    error_code=None,
                    error_message=None,
                )

            if not self._is_active_job(session_id=session_id, job_token=job_token):
                logger.info("Revision job completion skipped after superseded session_id=%s task_id=%s", session_id, task_id)
                return

            self._repository.save_revision(
                session_id=session_id,
                task_id=task_id,
                user_prompt=user_prompt,
                status=int(RevisionStatus.COMPLETED),
                items=current_items,
                error_code=None,
                error_message=None,
            )
        except Exception as exc:
            logger.exception("Revision background job failed session_id=%s task_id=%s", session_id, task_id)
            if self._is_active_job(session_id=session_id, job_token=job_token):
                self._repository.save_revision(
                    session_id=session_id,
                    task_id=task_id,
                    user_prompt=user_prompt,
                    status=int(RevisionStatus.FAILED),
                    items=current_items,
                    error_code="revision_generation_failed",
                    error_message=str(exc),
                )
        finally:
            self._clear_job(session_id=session_id, job_token=job_token)

    def _build_prompt_utterances(
        self,
        utterances: list[TaskTranscriptUtterance],
    ) -> list[RevisionPromptUtterance]:
        return [
            RevisionPromptUtterance(
                utterance_seq=int(item.seq),
                speaker=item.speaker,
                text=item.text,
                addions=self._filter_revision_addions(item.additions),
            )
            for item in utterances
        ]

    def _build_initial_revision_items(
        self,
        *,
        task_id: str,
        utterances: list[TaskTranscriptUtterance],
    ) -> list[GeneratedRevisionItem]:
        return [
            GeneratedRevisionItem(
                task_id=task_id,
                source_seq_start=int(item.seq),
                source_seq_end=int(item.seq),
                source_seq_count=1,
                source_seqs=[int(item.seq)],
                speaker=item.speaker,
                start_time=int(item.start_time),
                end_time=int(item.end_time),
                original_text=item.text,
                suggested_text=item.text,
                suggested_cue=None,
                score=0,
                issue_tags="",
                explanations="",
            )
            for item in utterances
        ]

    @staticmethod
    def _build_generated_revision_item(
        *,
        task_id: str,
        utterance_by_seq: dict[int, TaskTranscriptUtterance],
        suggestion: RevisionSuggestion,
    ) -> GeneratedRevisionItem:
        source_seqs = [int(seq) for seq in suggestion.source_seqs]
        ordered_utterances = [
            utterance_by_seq[int(seq)]
            for seq in source_seqs
            if int(seq) in utterance_by_seq
        ]
        if len(ordered_utterances) != len(source_seqs):
            raise RuntimeError(f"Unable to locate all source utterances for revision span: {source_seqs}")

        ordered_utterances.sort(key=lambda item: int(item.seq))
        speaker = ordered_utterances[0].speaker
        return GeneratedRevisionItem(
            task_id=task_id,
            source_seq_start=source_seqs[0],
            source_seq_end=source_seqs[-1],
            source_seq_count=len(source_seqs),
            source_seqs=source_seqs,
            speaker=speaker,
            start_time=min(int(item.start_time) for item in ordered_utterances),
            end_time=max(int(item.end_time) for item in ordered_utterances),
            original_text=RevisionService._join_original_text([item.text for item in ordered_utterances]),
            suggested_text=suggestion.suggested_text,
            suggested_cue=suggestion.suggested_cue,
            score=int(suggestion.score),
            issue_tags=suggestion.issue_tags,
            explanations=suggestion.explanations,
        )

    @staticmethod
    def _merge_generated_items(
        *,
        current_items: list[GeneratedRevisionItem],
        incoming_items: list[GeneratedRevisionItem],
    ) -> list[GeneratedRevisionItem]:
        incoming_source_seqs = {
            int(seq)
            for item in incoming_items
            for seq in item.source_seqs
        }
        merged_items = [
            item
            for item in current_items
            if incoming_source_seqs.isdisjoint({int(seq) for seq in item.source_seqs})
        ]
        merged_items.extend(incoming_items)
        return RevisionService._sort_generated_items(merged_items)

    @staticmethod
    def _sort_generated_items(items: list[GeneratedRevisionItem]) -> list[GeneratedRevisionItem]:
        return sorted(
            items,
            key=lambda item: (
                int(item.source_seq_start),
                int(item.source_seq_end),
            ),
        )

    @staticmethod
    def _join_original_text(parts: list[str]) -> str:
        return " ".join(part.strip() for part in parts if part and part.strip())

    @staticmethod
    def _filter_revision_addions(addions: dict[str, object] | None) -> dict[str, str | int | float]:
        if not addions:
            return {}

        filtered: dict[str, str | int | float] = {}
        for key in ("emotion", "emotion_degree"):
            value = addions.get(key)
            if value is None:
                continue
            if isinstance(value, (str, int, float)):
                filtered[key] = value
        return filtered

    def _register_job(self, session_id: str) -> str:
        job_token = str(uuid.uuid4())
        with self._job_tokens_lock:
            self._job_tokens[session_id] = job_token
        return job_token

    def _is_active_job(self, *, session_id: str, job_token: str) -> bool:
        with self._job_tokens_lock:
            return self._job_tokens.get(session_id) == job_token

    def _clear_job(self, *, session_id: str, job_token: str) -> None:
        with self._job_tokens_lock:
            if self._job_tokens.get(session_id) == job_token:
                self._job_tokens.pop(session_id, None)

    def _to_revision_data(self, model: UtterancesRevisionModel) -> RevisionData:
        items = [
            self._to_revision_item_data(item)
            for item in sorted(
                model.items,
                key=lambda value: (
                    value.source_seq_start,
                    value.source_seq_end,
                ),
            )
        ]
        return RevisionData.build(
            revision_id=str(model.revision_id),
            session_id=str(model.session_id),
            task_id=str(model.task_id),
            user_prompt=model.user_prompt,
            status=int(model.status),
            error_code=model.error_code,
            error_message=model.error_message,
            item_count=int(model.item_count),
            created_at=model.created_at,
            updated_at=model.updated_at,
            items=items,
        )

    @staticmethod
    def _to_revision_item_data(model: UtterancesRevisionItemModel) -> RevisionItemData:
        return RevisionItemData(
            item_id=str(model.item_id),
            revision_id=str(model.revision_id),
            task_id=str(model.task_id),
            source_seq_start=int(model.source_seq_start),
            source_seq_end=int(model.source_seq_end),
            source_seq_count=int(model.source_seq_count),
            source_seqs=[int(seq) for seq in (model.source_seqs or [])],
            speaker=model.speaker,
            start_time=int(model.start_time),
            end_time=int(model.end_time),
            original_text=model.original_text,
            suggested_text=model.suggested_text,
            suggested_cue=model.suggested_cue,
            draft_text=model.draft_text,
            draft_cue=model.draft_cue,
            score=int(model.score),
            issue_tags=model.issue_tags,
            explanations=model.explanations,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
