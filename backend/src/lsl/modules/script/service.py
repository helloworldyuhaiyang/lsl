from __future__ import annotations

import re

from lsl.modules.revision.service import RevisionService
from lsl.modules.revision.types import GeneratedRevisionItem
from lsl.modules.script.schema import GenerateScriptSessionData, GenerateScriptSessionRequest
from lsl.modules.script.types import GeneratedScriptTurn, ScriptGenerateRequest, ScriptGenerator
from lsl.modules.session.schema import CreateSessionRequest
from lsl.modules.session.service import SessionService
from lsl.modules.task.schema import TaskTranscriptUtterance
from lsl.modules.task.service import TaskService

_WORD_PATTERN = re.compile(r"[A-Za-z0-9']+")


class ScriptService:
    def __init__(
        self,
        *,
        generator: ScriptGenerator,
        session_service: SessionService,
        task_service: TaskService,
        revision_service: RevisionService,
    ) -> None:
        self._generator = generator
        self._session_service = session_service
        self._task_service = task_service
        self._revision_service = revision_service

    def generate_session(self, payload: GenerateScriptSessionRequest) -> GenerateScriptSessionData:
        req = ScriptGenerateRequest(
            title=payload.title,
            description=payload.description,
            language=payload.language,
            prompt=payload.prompt,
            turn_count=payload.turn_count,
            speaker_count=payload.speaker_count,
            difficulty=payload.difficulty,
            cue_style=payload.cue_style,
            must_include=payload.must_include,
        )
        generated_script = self._generator.generate(req)
        transcript_utterances = self._build_transcript_utterances(generated_script.utterances)
        task = self._task_service.create_text_task(
            utterances=transcript_utterances,
            language=payload.language,
            full_text="\n".join(item.text for item in transcript_utterances),
            raw_result={
                "provider": self._generator.provider_name,
                "prompt": payload.prompt,
                "utterances": [
                    {
                        "speaker": item.speaker,
                        "cue": item.cue,
                        "text": item.text,
                    }
                    for item in generated_script.utterances
                ],
            },
        )
        session = self._session_service.create_session(
            CreateSessionRequest(
                title=payload.title,
                description=payload.description,
                language=payload.language,
                f_type=2,
                current_task_id=task.task_id,
            )
        )
        revision = self._revision_service.create_generated_revision(
            session_id=session.session.session_id,
            task_id=task.task_id,
            user_prompt=payload.prompt,
            items=self._build_revision_items(
                task_id=task.task_id,
                transcript_utterances=transcript_utterances,
                generated_turns=generated_script.utterances,
            ),
        )
        session_data = self._session_service.get_session(session.session.session_id, auto_refresh=False)
        return GenerateScriptSessionData(session=session_data, revision=revision)

    @staticmethod
    def _build_transcript_utterances(
        generated_turns: list[GeneratedScriptTurn],
    ) -> list[TaskTranscriptUtterance]:
        utterances: list[TaskTranscriptUtterance] = []
        current_start_ms = 0
        for index, item in enumerate(generated_turns):
            duration_ms = ScriptService._estimate_duration_ms(item.text)
            utterances.append(
                TaskTranscriptUtterance(
                    seq=index,
                    text=item.text.strip(),
                    speaker=item.speaker.strip() or f"user-{(index % 2) + 1}",
                    start_time=current_start_ms,
                    end_time=current_start_ms + duration_ms,
                    additions={"cue": item.cue.strip()},
                )
            )
            current_start_ms += duration_ms
        return utterances

    @staticmethod
    def _build_revision_items(
        *,
        task_id: str,
        transcript_utterances: list[TaskTranscriptUtterance],
        generated_turns: list[GeneratedScriptTurn],
    ) -> list[GeneratedRevisionItem]:
        if len(transcript_utterances) != len(generated_turns):
            raise RuntimeError("Generated script and transcript utterances length mismatch")

        items: list[GeneratedRevisionItem] = []
        for transcript_item, generated_turn in zip(transcript_utterances, generated_turns, strict=True):
            suggested_text = ScriptService._compose_cue_script(
                cue=generated_turn.cue,
                text=generated_turn.text,
            )
            items.append(
                GeneratedRevisionItem(
                    task_id=task_id,
                    source_seq_start=int(transcript_item.seq),
                    source_seq_end=int(transcript_item.seq),
                    source_seq_count=1,
                    source_seqs=[int(transcript_item.seq)],
                    speaker=transcript_item.speaker,
                    start_time=int(transcript_item.start_time),
                    end_time=int(transcript_item.end_time),
                    original_text=transcript_item.text,
                    suggested_text=suggested_text,
                    draft_text=None,
                    score=100,
                    issue_tags="",
                    explanations="AI generated cue script.",
                )
            )
        return items

    @staticmethod
    def _compose_cue_script(*, cue: str, text: str) -> str:
        normalized_cue = cue.strip().strip("[]")
        normalized_text = re.sub(r"\s+", " ", text.strip())
        return f"[{normalized_cue}] {normalized_text}".strip()

    @staticmethod
    def _estimate_duration_ms(text: str) -> int:
        word_count = len(_WORD_PATTERN.findall(text))
        if word_count <= 0:
            return 1400
        return max(1400, min(6000, word_count * 420))
