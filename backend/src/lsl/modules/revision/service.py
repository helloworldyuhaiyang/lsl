from __future__ import annotations

from dataclasses import dataclass
import logging
import re

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


@dataclass(slots=True)
class PromptProfile:
    mode: str = "default"
    scene: str | None = None


@dataclass(slots=True)
class SentenceSuggestion:
    suggested_text: str
    issue_tags: list[str]
    explanations: list[str]


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
        profile = self._build_prompt_profile(user_prompt)
        generated_by_seq = self._generate_with_llm(
            task_id=task_id,
            utterances=utterances,
            user_prompt=user_prompt,
        )
        items: list[GeneratedRevisionItem] = []
        for utterance in utterances:
            local_suggestion = self._build_local_suggestion(
                utterance=utterance,
                profile=profile,
                user_prompt=user_prompt,
            )
            suggestion = generated_by_seq.get(
                int(utterance.seq),
                local_suggestion,
            )
            items.append(
                GeneratedRevisionItem(
                    task_id=task_id,
                    utterance_seq=int(utterance.seq),
                    speaker=self._normalize_speaker(utterance.speaker),
                    start_time=int(utterance.start_time),
                    end_time=int(utterance.end_time),
                    original_text=utterance.text,
                    suggested_text=suggestion.suggested_text,
                    suggested_cue=suggestion.suggested_cue or local_suggestion.suggested_cue,
                    score=int(suggestion.score),
                    issue_tags=suggestion.issue_tags or local_suggestion.issue_tags,
                    explanations=suggestion.explanations or local_suggestion.explanations,
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
                    speaker=self._normalize_speaker(item.speaker),
                    text=item.text,
                    start_time=int(item.start_time),
                    end_time=int(item.end_time),
                )
                for item in utterances
            ],
        )
        try:
            suggestions = self._generator.generate(req)
        except NotImplementedError:
            return {}
        except Exception as exc:
            logger.warning("Revision generator failed for task %s: %s", task_id, exc)
            return {}

        return {int(item.utterance_seq): item for item in suggestions}

    def _build_local_suggestion(
        self,
        *,
        utterance: TaskTranscriptUtterance,
        profile: PromptProfile,
        user_prompt: str | None,
    ) -> RevisionSuggestion:
        suggestion = self._suggest_sentence(utterance.text, profile=profile, user_prompt=user_prompt)
        suggested_cue = self._infer_expression_cue(suggestion.suggested_text, profile=profile)
        return RevisionSuggestion(
            utterance_seq=int(utterance.seq),
            suggested_text=suggestion.suggested_text,
            suggested_cue=suggested_cue,
            score=self._score_revision_issues(suggestion.issue_tags),
            issue_tags=suggestion.issue_tags,
            explanations=suggestion.explanations,
        )

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
            issue_tags=list(model.issue_tags_json or []),
            explanations=list(model.explanations_json or []),
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def _normalize_speaker(speaker: str | None) -> str | None:
        if speaker is None:
            return None
        normalized = speaker.replace("_", " ").strip()
        return normalized or None

    @staticmethod
    def _ensure_sentence_punctuation(text: str) -> str:
        trimmed = text.strip()
        if not trimmed:
            return trimmed
        if re.search(r"[.!?]$", trimmed):
            return trimmed
        return f"{trimmed}."

    @staticmethod
    def _capitalize_first(text: str) -> str:
        trimmed = text.strip()
        if not trimmed:
            return trimmed
        return f"{trimmed[0].upper()}{trimmed[1:]}"

    def _apply_prompt_style(self, text: str, *, profile: PromptProfile) -> tuple[str, list[str]]:
        updated = text
        notes: list[str] = []

        if profile.mode == "casual":
            replacements = (
                ("I do not", "I don't"),
                ("I cannot", "I can't"),
                ("I will", "I'll"),
            )
            changed = False
            for source, target in replacements:
                if source in updated:
                    updated = updated.replace(source, target)
                    changed = True
            if changed:
                notes.append("Adjusted phrasing to sound more conversational.")

        if profile.mode == "formal":
            replacements = (
                ("I don't", "I do not"),
                ("I can't", "I cannot"),
                ("I'm", "I am"),
            )
            changed = False
            for source, target in replacements:
                if source in updated:
                    updated = updated.replace(source, target)
                    changed = True
            if changed:
                notes.append("Adjusted phrasing to sound more formal.")

        if profile.mode == "concise":
            concise = re.sub(r"\b(Actually|Basically|Honestly),?\s+", "", updated, flags=re.IGNORECASE).strip()
            if concise and concise != updated:
                updated = concise
                notes.append("Removed filler phrasing for a more concise answer.")

        return updated, notes

    def _build_prompt_profile(self, user_prompt: str | None) -> PromptProfile:
        normalized = (user_prompt or "").strip().lower()
        if not normalized:
            return PromptProfile()
        if any(token in normalized for token in ("casual", "daily", "口语", "日常", "自然")):
            return PromptProfile(mode="casual", scene="日常对话")
        if any(token in normalized for token in ("formal", "professional", "正式", "面试", "interview")):
            return PromptProfile(mode="formal", scene="正式表达")
        if any(token in normalized for token in ("concise", "short", "简洁", "简短")):
            return PromptProfile(mode="concise", scene="简洁回答")
        return PromptProfile()

    def _suggest_sentence(
        self,
        original: str,
        *,
        profile: PromptProfile,
        user_prompt: str | None,
    ) -> SentenceSuggestion:
        next_text = original.strip()
        explanations: list[str] = []

        replacements: list[tuple[str, str, str]] = [
            (r"\bI go to\b", "I went to", "Adjusted present tense to past tense in context."),
            (r"\bto to\b", "to", "Removed duplicated word."),
            (r"\bI very like\b", "I really like", "Improved unnatural phrasing."),
            (r"\bpeople is\b", "people are", "Corrected subject-verb agreement."),
            (r"\bwant improve\b", "want to improve", "Inserted missing infinitive marker."),
            (r"\bspoken english\b", "spoken English", "Corrected capitalization."),
        ]

        for pattern, replacement, note in replacements:
            if re.search(pattern, next_text, flags=re.IGNORECASE):
                next_text = re.sub(pattern, replacement, next_text, flags=re.IGNORECASE)
                explanations.append(note)

        capitalized = self._capitalize_first(next_text)
        if capitalized != next_text:
            next_text = capitalized
            explanations.append("Corrected capitalization.")
        punctuated = self._ensure_sentence_punctuation(next_text)
        if punctuated != next_text:
            next_text = punctuated
            explanations.append("Added ending punctuation.")

        styled_text, prompt_notes = self._apply_prompt_style(next_text, profile=profile)
        if styled_text != next_text:
            next_text = styled_text
        explanations.extend(prompt_notes)

        if user_prompt:
            explanations.append(f'Applied user prompt: "{user_prompt}".')

        issue_tags = self._infer_issue_tags(explanations)
        if not explanations:
            explanations.append("No strong rewrite needed; kept sentence natural and clear.")

        return SentenceSuggestion(suggested_text=next_text, issue_tags=issue_tags, explanations=explanations)

    @staticmethod
    def _infer_issue_tags(explanations: list[str]) -> list[str]:
        issues: list[str] = []
        lowered = " ".join(explanations).lower()

        if any(token in lowered for token in ("tense", "agreement", "infinitive", "grammar")):
            issues.append("语法错误")
        if "unnatural phrasing" in lowered:
            issues.append("不够自然")
        if "capitalization" in lowered:
            issues.append("大小写问题")
        if "punctuation" in lowered:
            issues.append("标点问题")

        if not issues:
            issues.append("表达基本自然")
        return issues

    @staticmethod
    def _score_revision_issues(issue_tags: list[str]) -> int:
        score = 96
        for issue in issue_tags:
            if issue == "语法错误":
                score -= 24
            elif issue == "不够自然":
                score -= 14
            elif issue == "标点问题":
                score -= 8
            elif issue == "大小写问题":
                score -= 6
        if "表达基本自然" in issue_tags:
            score = max(score, 92)
        return max(35, min(score, 99))

    @staticmethod
    def _infer_expression_cue(text: str, *, profile: PromptProfile) -> str:
        normalized = text.strip().lower()
        scene = profile.scene or "日常对话"

        if any(token in normalized for token in ("thank", "thanks", "appreciate")):
            return f"[真诚的 / 礼貌的 / {scene}]"
        if any(token in normalized for token in ("sorry", "apologize", "excuse me")):
            return f"[抱歉的 / 柔和的 / {scene}]"
        if "?" in text:
            return f"[关心的 / 好奇的 / {scene}]"
        if any(token in normalized for token in ("weekend", "friends", "trip", "travel")):
            return f"[积极的 / 分享经历的 / {scene}]"
        return f"[自然的 / 平稳的 / {scene}]"
