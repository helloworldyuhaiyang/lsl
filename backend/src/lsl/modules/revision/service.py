from __future__ import annotations

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
            and int(existing.status) == int(RevisionStatus.COMPLETED)
            and len(existing.items) > 0
        ):
            return self._to_revision_data(existing)

        transcript = self._task_service.get_transcript(task_id=task_id, include_raw=False)
        generated_items = self._generate_revision_items(
            task_id=task_id,
            utterances=transcript.utterances,
            user_prompt=user_prompt,
        )
        model = self._repository.save_revision(
            session_id=session_id,
            task_id=task_id,
            user_prompt=user_prompt,
            status=int(RevisionStatus.COMPLETED),
            items=generated_items,
        )
        return self._to_revision_data(model)

    def update_revision_item(self, *, item_id: str, payload: UpdateRevisionItemRequest) -> RevisionItemData:
        updates = payload.model_dump(exclude_unset=True)
        if not updates:
            raise ValueError("draft_text or draft_cue is required")

        item = self._repository.update_revision_item(item_id=item_id, updates=updates)
        if item is None:
            raise ValueError("revision item not found")
        return self._to_revision_item_data(item)

    def _generate_revision_items(
        self,
        *,
        task_id: str,
        utterances: list[TaskTranscriptUtterance],
        user_prompt: str | None,
    ) -> list[GeneratedRevisionItem]:
        generated_by_seq = self._generate_with_llm(
            task_id=task_id,
            utterances=utterances,
            user_prompt=user_prompt,
        )
        missing_seqs = [int(utterance.seq) for utterance in utterances if int(utterance.seq) not in generated_by_seq]
        if missing_seqs:
            joined = ", ".join(str(seq) for seq in missing_seqs)
            raise RuntimeError(f"LLM revision missing utterance_seq: {joined}")

        items: list[GeneratedRevisionItem] = []
        for utterance in utterances:
            suggestion = generated_by_seq[int(utterance.seq)]
            items.append(
                GeneratedRevisionItem(
                    task_id=task_id,
                    utterance_seq=int(utterance.seq),
                    speaker=utterance.speaker,
                    start_time=int(utterance.start_time),
                    end_time=int(utterance.end_time),
                    original_text=utterance.text,
                    suggested_text=suggestion.suggested_text,
                    suggested_cue=suggestion.suggested_cue,
                    score=int(suggestion.score),
                    issue_tags=suggestion.issue_tags,
                    explanations=suggestion.explanations,
                )
            )
        return items

    def _generate_with_llm(
        self,
        *,
        task_id: str,
        utterances: list[TaskTranscriptUtterance],
        user_prompt: str | None,
    ) -> dict[int, RevisionSuggestion]:
        req = RevisionGenerateRequest(
            task_id=task_id,
            user_prompt=user_prompt,
            utterances=[
                RevisionPromptUtterance(
                    utterance_seq=int(item.seq),
                    speaker=item.speaker,
                    text=item.text,
                    addions=self._filter_revision_addions(item.additions),
                )
                for item in utterances
            ],
        )
        suggestions = self._generator.generate(req)
        return {int(item.utterance_seq): item for item in suggestions}

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

    def _to_revision_data(self, model: UtterancesRevisionModel) -> RevisionData:
        items = [self._to_revision_item_data(item) for item in sorted(model.items, key=lambda value: value.utterance_seq)]
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
            utterance_seq=int(model.utterance_seq),
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
