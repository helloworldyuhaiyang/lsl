from __future__ import annotations

import logging

from lsl.modules.job.service import JobService
from lsl.modules.job.types import JobData, JobRunResult, JobStatus
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
from lsl.modules.transcript.schema import TranscriptUtteranceData
from lsl.modules.transcript.service import TranscriptService

logger = logging.getLogger(__name__)


class RevisionService:
    def __init__(
        self,
        *,
        repository: RevisionRepository,
        generator: RevisionGenerator,
        session_service: SessionService,
        transcript_service: TranscriptService,
        job_service: JobService | None = None,
    ) -> None:
        self._repository = repository
        self._generator = generator
        self._session_service = session_service
        self._transcript_service = transcript_service
        self._job_service = job_service

    def shutdown(self) -> None:
        return None

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
        transcript_id = session_data.session.current_transcript_id
        if transcript_id is None:
            raise ValueError("session current_transcript_id is missing")

        existing = self._repository.get_revision_by_session_id(session_id)
        if (
            existing is not None
            and not force
            and str(existing.transcript_id) == transcript_id
            and (existing.user_prompt or None) == user_prompt
        ):
            if int(existing.status) == int(RevisionStatus.COMPLETED) and len(existing.items) > 0:
                return self._to_revision_data(existing)
            if int(existing.status) == int(RevisionStatus.GENERATING):
                return self._to_revision_data(existing)

        if self._job_service is None:
            raise RuntimeError("Job service is not initialized")

        # Revision job flow 2/5: store an empty generating revision first.
        # This hides old cards while the job progressively fills revision_items.
        model = self._repository.save_revision(
            session_id=session_id,
            transcript_id=transcript_id,
            user_prompt=user_prompt,
            status=int(RevisionStatus.GENERATING),
            items=[],
            preserve_existing_drafts=False,
            error_code=None,
            error_message=None,
        )
        revision = self._to_revision_data(model)

        # Revision job flow 3/5: create a generic job. The job runner later
        # dispatches it to RevisionJobHandler by job_type.
        job = self._job_service.create_job(
            job_type=RevisionJobHandler.job_type,
            entity_type="revision",
            entity_id=revision.revision_id,
            payload={
                "session_id": session_id,
                "transcript_id": transcript_id,
                "revision_id": revision.revision_id,
            },
        )

        # The revision row points to the active job so stale jobs can be ignored.
        model = self._repository.set_job_id(session_id=session_id, job_id=job.job_id)
        logger.info(
            "Revision generation job created session_id=%s transcript_id=%s revision_id=%s job_id=%s",
            session_id,
            transcript_id,
            revision.revision_id,
            job.job_id,
        )

        return self._to_revision_data(model)

    def create_generated_revision(
        self,
        *,
        session_id: str,
        transcript_id: str,
        user_prompt: str | None,
        items: list[GeneratedRevisionItem],
    ) -> RevisionData:
        session_data = self._session_service.get_session(session_id, auto_refresh=False)
        current_transcript_id = session_data.session.current_transcript_id
        if current_transcript_id is None:
            raise ValueError("session current_transcript_id is missing")
        if str(current_transcript_id) != str(transcript_id):
            raise ValueError("session current_transcript_id does not match transcript_id")

        model = self._repository.save_revision(
            session_id=session_id,
            transcript_id=transcript_id,
            user_prompt=user_prompt,
            status=int(RevisionStatus.COMPLETED),
            items=items,
            preserve_existing_drafts=False,
            error_code=None,
            error_message=None,
        )
        model = self._repository.set_job_id(session_id=session_id, job_id=None)
        return self._to_revision_data(model)

    def update_revision_item(self, *, item_id: str, payload: UpdateRevisionItemRequest) -> RevisionItemData:
        updates = payload.model_dump(exclude_unset=True)
        if not updates:
            raise ValueError("draft_text is required")

        item = self._repository.update_revision_item(item_id=item_id, updates=updates)
        if item is None:
            raise ValueError("revision item not found")
        return self._to_revision_item_data(item)

    def run_generation_job(
        self,
        *,
        session_id: str,
        transcript_id: str,
        job_id: str,
    ) -> JobRunResult:
        # Revision job flow 5/5: a claimed revision_generation job runs here.
        revision = self._repository.get_revision_by_session_id(session_id)
        if revision is None:
            return JobRunResult(status=JobStatus.FAILED, error_code="REVISION_NOT_FOUND", error_message="revision not found")
        # If another POST /revisions replaced job_id, this job must not write stale output.
        if str(revision.job_id or "") != job_id:
            logger.info(
                "Revision generation job canceled because it is superseded session_id=%s transcript_id=%s job_id=%s active_job_id=%s",
                session_id,
                transcript_id,
                job_id,
                revision.job_id,
            )
            return JobRunResult(status=JobStatus.CANCELED, error_message="revision job superseded")
        user_prompt = revision.user_prompt
        transcript = self._transcript_service.get_transcript(transcript_id=transcript_id, include_raw=False)
        utterances = transcript.utterances
        current_items = self._generated_items_from_model(revision)
        prompt_utterances = self._build_prompt_utterances(utterances)
        utterance_by_seq = {int(item.seq): item for item in utterances}
        req = RevisionGenerateRequest(
            transcript_id=transcript_id,
            user_prompt=user_prompt,
            utterances=prompt_utterances,
        )

        try:
            # The generator yields segment batches; every batch is saved so GET /revisions
            # can show partial results while the job is still generating.
            for segment_suggestions in self._generator.generate_progressively(req):
                if not self._is_active_revision_job(session_id=session_id, job_id=job_id):
                    logger.info("Revision job superseded session_id=%s transcript_id=%s job_id=%s", session_id, transcript_id, job_id)
                    return JobRunResult(status=JobStatus.CANCELED, error_message="revision job superseded")

                generated_segment_items = [
                    self._build_generated_revision_item(
                        transcript_id=transcript_id,
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
                    transcript_id=transcript_id,
                    user_prompt=user_prompt,
                    status=int(RevisionStatus.GENERATING),
                    items=current_items,
                    preserve_existing_drafts=False,
                    error_code=None,
                    error_message=None,
                )

            # Returning COMPLETED lets JobService mark job_jobs.status as completed.
            if not self._is_active_revision_job(session_id=session_id, job_id=job_id):
                logger.info("Revision job completion skipped after superseded session_id=%s transcript_id=%s job_id=%s", session_id, transcript_id, job_id)
                return JobRunResult(status=JobStatus.CANCELED, error_message="revision job superseded")

            self._repository.save_revision(
                session_id=session_id,
                transcript_id=transcript_id,
                user_prompt=user_prompt,
                status=int(RevisionStatus.COMPLETED),
                items=current_items,
                preserve_existing_drafts=False,
                error_code=None,
                error_message=None,
            )
            return JobRunResult(status=JobStatus.COMPLETED, progress=100)
        except Exception as exc:
            logger.exception("Revision generation job failed session_id=%s transcript_id=%s job_id=%s", session_id, transcript_id, job_id)
            if self._is_active_revision_job(session_id=session_id, job_id=job_id):
                self._repository.save_revision(
                    session_id=session_id,
                    transcript_id=transcript_id,
                    user_prompt=user_prompt,
                    status=int(RevisionStatus.FAILED),
                    items=current_items,
                    preserve_existing_drafts=False,
                    error_code="revision_generation_failed",
                    error_message=str(exc),
                )
            return JobRunResult(status=JobStatus.FAILED, error_code="REVISION_GENERATION_FAILED", error_message=str(exc))

    def _build_prompt_utterances(
        self,
        utterances: list[TranscriptUtteranceData],
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

    @staticmethod
    def _build_generated_revision_item(
        *,
        transcript_id: str,
        utterance_by_seq: dict[int, TranscriptUtteranceData],
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
            transcript_id=transcript_id,
            source_seq_start=source_seqs[0],
            source_seq_end=source_seqs[-1],
            source_seq_count=len(source_seqs),
            source_seqs=source_seqs,
            speaker=speaker,
            start_time=min(int(item.start_time) for item in ordered_utterances),
            end_time=max(int(item.end_time) for item in ordered_utterances),
            original_text=RevisionService._join_original_text([item.text for item in ordered_utterances]),
            suggested_text=suggestion.suggested_text,
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

    def _is_active_revision_job(self, *, session_id: str, job_id: str) -> bool:
        model = self._repository.get_revision_by_session_id(session_id)
        return model is not None and str(model.job_id or "") == job_id

    @staticmethod
    def _generated_items_from_model(model: UtterancesRevisionModel) -> list[GeneratedRevisionItem]:
        return [
            GeneratedRevisionItem(
                transcript_id=str(item.transcript_id),
                source_seq_start=int(item.source_seq_start),
                source_seq_end=int(item.source_seq_end),
                source_seq_count=int(item.source_seq_count),
                source_seqs=[int(seq) for seq in (item.source_seqs or [])],
                speaker=item.speaker,
                start_time=int(item.start_time),
                end_time=int(item.end_time),
                original_text=item.original_text,
                suggested_text=item.suggested_text,
                draft_text=item.draft_text,
                score=int(item.score),
                issue_tags=item.issue_tags,
                explanations=item.explanations,
            )
            for item in model.items
        ]

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
            transcript_id=str(model.transcript_id),
            job_id=str(model.job_id) if model.job_id is not None else None,
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
            transcript_id=str(model.transcript_id),
            source_seq_start=int(model.source_seq_start),
            source_seq_end=int(model.source_seq_end),
            source_seq_count=int(model.source_seq_count),
            source_seqs=[int(seq) for seq in (model.source_seqs or [])],
            speaker=model.speaker,
            start_time=int(model.start_time),
            end_time=int(model.end_time),
            original_text=model.original_text,
            suggested_text=model.suggested_text,
            draft_text=model.draft_text,
            score=int(model.score),
            issue_tags=model.issue_tags,
            explanations=model.explanations,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )


class RevisionJobHandler:
    job_type = "revision_generation"

    def __init__(self, *, revision_service: RevisionService) -> None:
        self._revision_service = revision_service

    def run(self, job: JobData) -> JobRunResult:
        # JobService calls this handler for jobs whose job_type is revision_generation.
        session_id = str(job.payload.get("session_id") or "").strip()
        transcript_id = str(job.payload.get("transcript_id") or "").strip()
        if not session_id or not transcript_id:
            return JobRunResult(
                status=JobStatus.FAILED,
                error_code="MISSING_REVISION_JOB_PAYLOAD",
                error_message="session_id and transcript_id are required",
            )
        return self._revision_service.run_generation_job(
            session_id=session_id,
            transcript_id=transcript_id,
            job_id=job.job_id,
        )
