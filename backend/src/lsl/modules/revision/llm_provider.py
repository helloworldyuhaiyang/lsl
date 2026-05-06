from __future__ import annotations

import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from queue import Empty, Queue
from time import perf_counter
from typing import Any

import httpx
from json_repair import repair_json
from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam
from openai.types.chat.chat_completion_system_message_param import ChatCompletionSystemMessageParam
from openai.types.chat.chat_completion_user_message_param import ChatCompletionUserMessageParam

from lsl.core.config import Settings
from lsl.modules.revision.types import (
    RevisionGenerateRequest,
    RevisionGenerator,
    RevisionPromptUtterance,
    RevisionSegment,
    RevisionSuggestion,
)

logger = logging.getLogger(__name__)

_CODE_FENCE_JSON_RE = re.compile(r"```(?:json)?\s*(.+?)\s*```", re.DOTALL | re.IGNORECASE)
_SPLIT_TEXT_RE = re.compile(r"[,/，、\n]+")
_MAX_ISSUE_TAGS = 4  # 每条 revise 建议最多保留的问题标签数，避免单条卡片标签过多。
_SEGMENT_HARD_MAX_UTTERANCE_COUNT = 10  # 提示 LLM 规划 segment 时不要超过的 utterance 数上限。
_SEGMENT_CONTEXT_UTTERANCE_COUNT = 2  # 每段 revise 前后额外带多少条上下文给模型参考。
_SEGMENT_MAX_WORKERS = 4  # 同一个 revision job 内最多并发多少个 segment revise 请求。
_SEGMENT_SUBMIT_STAGGER_SECONDS = 2.0  # 每次启动下一个 segment revise 请求前的最小间隔秒数。

_SEGMENT_PLAN_SYSTEM_PROMPT = (
"""You are planning revision batches for a transcript.

Your task is to divide the transcript into contiguous topic-based sections before sentence-level revision.

Important rules:
- Return a JSON object only.
- Cover every utterance exactly once.
- Segments must be contiguous by utterance_seq, with no gaps and no overlaps.
- Prefer split points where the topic, activity, or discussion phase changes.
- Keep each segment reasonably small for downstream revision.
"""
f"- Each segment must contain no more than {_SEGMENT_HARD_MAX_UTTERANCE_COUNT} utterances.\n"
"""
- Most segments should contain about 16 to 28 target utterances.
- Never merge unrelated topics just to reduce the number of segments.
- Give each segment a short title and a short summary.

Output schema:
{
  "segments": [
    {
      "segment_index": 1,
      "start_seq": 0,
      "end_seq": 23,
      "title": "Greeting and Status Check",
      "summary": "Content: Both speakers use a voice chat app to say hello, then discuss whether they are busy, work arrangements, etc. Result: speaker2's work today: 1) fixed software bugs; 2) discussed customer requirements with customers; 3) summarized meeting minutes. speaker1's work today: 1) completed a project test; 2) discussed project progress with colleagues; 3) prepared materials for tomorrow's meeting."
    }
  ]
}
"""
)

_SEGMENT_REVISION_SYSTEM_PROMPT_TEMPLATE = """You are an expert {spoken_language} speaking coach for oral {spoken_language} classes.

Your task is to revise only the target utterances and return NDJSON only.

Goals for each output item:
1. Rewrite the original text or utterance span into fluent, natural spoken {spoken_language}.
2. Preserve the original meaning, intent, and speaker perspective.
3. Score the ORIGINAL source utterance(s) from 0 to 100 based on grammar, clarity, and naturalness.
4. Provide short Chinese issue tags and short Chinese explanations for improvement.
5. Include one short {cue_language} delivery cue in every rewritten script.

Important rules:
- Use the segment title, segment summary, and nearby context only for understanding.
- Return items only for target_utterances. Do not return context utterances.
- Every target utterance_seq must be covered exactly once across all items. No gaps. No overlaps.
- Each item must contain source_seqs: a non-empty contiguous array of target utterance_seq values such as [4] or [4, 5].
- You may merge adjacent target utterances only when they clearly belong to the same speaker and form one natural spoken sentence or ASR-fragment span.
- Do not merge across different speakers.
- Never leave suggested_text empty.
- suggested_text must be a single editable script string that starts with exactly one delivery CUE in square brackets, such as "{suggested_text_example}"
- If a target utterance includes addions.cue or the source text already starts with a square-bracket CUE, translate or rewrite that CUE into {cue_language}; do not leave it in the wrong language.
- Keep the square-bracket CUE as delivery guidance, not spoken content.
- Keep edits minimal if the sentence is already natural.
- Do not invent facts, change tense without reason, or change the speaker's intent.
- Prefer one natural spoken sentence. Two short sentences are acceptable when needed.
- issue_tags should be one comma-separated Chinese string such as "不够自然, 语法错误".
- explanations should be one concise Chinese string.
- Use strict JSON objects that can be parsed by Python json.loads.
- Return one complete JSON object per line.
- Each line must be one revised item. Do not wrap items in an array or an object.
- Do not include trailing commas before }.
- Return NDJSON only. No markdown. No extra text.

Output schema, one JSON object per line:
{"source_seqs":[1],"suggested_text":"{suggested_text_example}","score":88,"issue_tags":"不够自然, 语法错误","explanations":"把表达改得更符合日常口语，并根据聊天上下文把时态调整正确。"}
"""


def create_revision_generator(settings: Settings) -> RevisionGenerator:
    provider = (settings.REVISION_PROVIDER or "fake").strip().lower()
    if provider == "llm":
        return LLMRevisionGenerator(settings)
    if provider == "fake":
        return FakeRevisionGenerator()
    raise ValueError(f"Unsupported REVISION_PROVIDER: {provider}")


class FakeRevisionGenerator:
    provider_name = "fake"

    def generate(self, req: RevisionGenerateRequest) -> list[RevisionSuggestion]:
        cue = "用夸张又兴奋的语气读这句" if _is_chinese_language(req.cue_language or req.target_language) else "Read this line with exaggerated excitement"
        text = "这是一个用于调试的假修订句子。" if _is_chinese_language(req.target_language) else "This is a fake revised sentence for debugging."
        suggestions: list[RevisionSuggestion] = []
        for item in req.utterances:
            suggestions.append(
                RevisionSuggestion(
                    source_seqs=[int(item.utterance_seq)],
                    suggested_text=f"[{cue}] {text}",
                    score=78,
                    issue_tags="调试文案",
                    explanations="Generated by FakeRevisionGenerator for local debugging.",
                )
            )
        return suggestions

    def generate_progressively(self, req: RevisionGenerateRequest):
        if not req.utterances:
            return
        yield self.generate(req)


class LLMRevisionGenerator:
    provider_name = "llm"

    def __init__(self, settings: Settings) -> None:
        self._api_key = settings.REVISION_LLM_API_KEY
        self._base_url = settings.REVISION_LLM_BASE_URL
        self._model = settings.REVISION_LLM_MODEL
        self._timeout = float(settings.REVISION_LLM_HTTP_TIMEOUT)
        self._debug_file = settings.REVISION_LLM_DEBUG_FILE.strip()
        self._client: OpenAI | None = None

    def generate(self, req: RevisionGenerateRequest) -> list[RevisionSuggestion]:
        suggestions: list[RevisionSuggestion] = []
        for segment_suggestions in self.generate_progressively(req):
            suggestions.extend(segment_suggestions)
        return self._deduplicate_suggestions(suggestions)

    def generate_progressively(self, req: RevisionGenerateRequest):
        if not req.utterances:
            return

        started_perf = perf_counter()
        logger.info(
            "Revision generation started transcript_id=%s utterance_count=%s provider=%s",
            req.transcript_id,
            len(req.utterances),
            self.provider_name,
        )
        # 短 transcript 直接作为一个 segment，避免额外的 segment_plan LLM 固定等待。
        # 只有超过 _SEGMENT_HARD_MAX_UTTERANCE_COUNT 时，才先让 LLM 做 topic-based 分段规划。
        segments = self._resolve_segments(
            transcript_id=req.transcript_id,
            utterances=req.utterances,
            user_prompt=req.user_prompt,
        )
        logger.info(
            "Revision segment plan ready transcript_id=%s segment_count=%s elapsed_ms=%s",
            req.transcript_id,
            len(segments),
            int((perf_counter() - started_perf) * 1000),
        )
        # 再按 segment 并发 revise；yield 粒度是 item batch，通常每解析出一个 NDJSON item 就 yield。
        # 这样 service 不需要等某段完整 JSON 全部结束，就能把已完成 items 增量写库。
        for segment_suggestions in self._generate_segmented_revisions(
            transcript_id=req.transcript_id,
            utterances=req.utterances,
            user_prompt=req.user_prompt,
            target_language=req.target_language,
            cue_language=req.cue_language,
            segments=segments,
        ):
            yield segment_suggestions

    def _resolve_segments(
        self,
        *,
        transcript_id: str,
        utterances: list[RevisionPromptUtterance],
        user_prompt: str | None,
    ) -> list[RevisionSegment]:
        if len(utterances) <= _SEGMENT_HARD_MAX_UTTERANCE_COUNT:
            segment = RevisionSegment(
                segment_index=1,
                start_seq=int(utterances[0].utterance_seq),
                end_seq=int(utterances[-1].utterance_seq),
                title="Full transcript",
                summary="Transcript is short enough to revise as one segment.",
            )
            logger.info(
                "Revision segment plan skipped transcript_id=%s utterance_count=%s hard_max=%s",
                transcript_id,
                len(utterances),
                _SEGMENT_HARD_MAX_UTTERANCE_COUNT,
            )
            return [segment]

        return self._plan_segments(
            transcript_id=transcript_id,
            utterances=utterances,
            user_prompt=user_prompt,
        )

    def _plan_segments(
        self,
        *,
        transcript_id: str,
        utterances: list[RevisionPromptUtterance],
        user_prompt: str | None,
    ) -> list[RevisionSegment]:
        content = self._request_chat_completion(
            transcript_id=transcript_id,
            request_name="segment_plan",
            messages=self._build_segment_plan_messages(
                transcript_id=transcript_id,
                utterances=utterances,
                user_prompt=user_prompt,
            ),
        )
        segments = self._parse_segment_plan_response(content=content, utterances=utterances)
        logger.info(
            "Revision segment plan parsed transcript_id=%s segment_count=%s utterance_count=%s",
            transcript_id,
            len(segments),
            len(utterances),
        )
        return segments

    def _generate_segmented_revisions(
        self,
        *,
        transcript_id: str,
        utterances: list[RevisionPromptUtterance],
        user_prompt: str | None,
        target_language: str | None,
        cue_language: str | None,
        segments: list[RevisionSegment],
    ):
        if not segments:
            return

        utterance_index_by_seq = {int(item.utterance_seq): index for index, item in enumerate(utterances)}
        # 同一个 revision job 内的段并发受 _SEGMENT_MAX_WORKERS 和实际 segment 数共同限制。
        max_workers = max(1, min(_SEGMENT_MAX_WORKERS, len(segments)))
        logger.info(
            "Revision segment revisions starting transcript_id=%s segment_count=%s max_workers=%s",
            transcript_id,
            len(segments),
            max_workers,
        )

        event_queue: Queue[tuple[str, RevisionSegment, RevisionSuggestion | Exception | None]] = Queue()
        segment_iter = iter(segments)
        active_count = 0
        submitted_count = 0
        completed_count = 0
        all_segments_submitted = False
        next_submit_at = 0.0
        executor = ThreadPoolExecutor(max_workers=max_workers)

        def run_segment(segment: RevisionSegment) -> None:
            try:
                for suggestion in self._generate_single_segment_revision_progressively(
                    transcript_id=transcript_id,
                    utterances=utterances,
                    user_prompt=user_prompt,
                    target_language=target_language,
                    cue_language=cue_language,
                    segment=segment,
                    utterance_index_by_seq=utterance_index_by_seq,
                ):
                    event_queue.put(("item", segment, suggestion))
                event_queue.put(("done", segment, None))
            except Exception as exc:
                event_queue.put(("error", segment, exc))

        def submit_next_segment() -> bool:
            nonlocal active_count, submitted_count, all_segments_submitted, next_submit_at
            try:
                segment = next(segment_iter)
            except StopIteration:
                all_segments_submitted = True
                return False

            submitted_count += 1
            active_count += 1
            if submitted_count >= len(segments):
                all_segments_submitted = True
            next_submit_at = perf_counter() + _SEGMENT_SUBMIT_STAGGER_SECONDS
            logger.info(
                "Revision segment submitted transcript_id=%s segment_index=%s seq_range=%s-%s submitted=%s/%s next_submit_delay_seconds=%s",
                transcript_id,
                segment.segment_index,
                segment.start_seq,
                segment.end_seq,
                submitted_count,
                len(segments),
                _SEGMENT_SUBMIT_STAGGER_SECONDS,
            )
            executor.submit(run_segment, segment)
            return True

        try:
            submit_next_segment()

            while active_count > 0 or not all_segments_submitted:
                now = perf_counter()
                if not all_segments_submitted and active_count < max_workers and now >= next_submit_at:
                    submit_next_segment()
                    continue

                timeout = None
                if not all_segments_submitted and active_count < max_workers:
                    timeout = max(0.0, next_submit_at - now)

                try:
                    event_name, segment, payload = event_queue.get(timeout=timeout)
                except Empty:
                    continue

                if event_name == "item":
                    if not isinstance(payload, RevisionSuggestion):
                        raise RuntimeError("Invalid revision segment item event")
                    yield [payload]
                    continue

                active_count -= 1
                if event_name == "done":
                    completed_count += 1
                    logger.info(
                        "Revision segment completed transcript_id=%s segment_index=%s seq_range=%s-%s completed=%s/%s",
                        transcript_id,
                        segment.segment_index,
                        segment.start_seq,
                        segment.end_seq,
                        completed_count,
                        len(segments),
                    )
                    continue

                if event_name == "error":
                    if isinstance(payload, Exception):
                        raise RuntimeError(
                            f"Segment revision failed for seq range {segment.start_seq}-{segment.end_seq}: {payload}"
                        ) from payload
                    raise RuntimeError(f"Segment revision failed for seq range {segment.start_seq}-{segment.end_seq}")

                raise RuntimeError(f"Unexpected revision segment event: {event_name}")
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    def _generate_single_segment_revision(
        self,
        *,
        transcript_id: str,
        utterances: list[RevisionPromptUtterance],
        user_prompt: str | None,
        target_language: str | None,
        cue_language: str | None,
        segment: RevisionSegment,
        utterance_index_by_seq: dict[int, int],
    ) -> list[RevisionSuggestion]:
        return list(
            self._generate_single_segment_revision_progressively(
                transcript_id=transcript_id,
                utterances=utterances,
                user_prompt=user_prompt,
                target_language=target_language,
                cue_language=cue_language,
                segment=segment,
                utterance_index_by_seq=utterance_index_by_seq,
            )
        )

    def _generate_single_segment_revision_progressively(
        self,
        *,
        transcript_id: str,
        utterances: list[RevisionPromptUtterance],
        user_prompt: str | None,
        target_language: str | None,
        cue_language: str | None,
        segment: RevisionSegment,
        utterance_index_by_seq: dict[int, int],
    ):
        start_index = utterance_index_by_seq.get(int(segment.start_seq))
        end_index = utterance_index_by_seq.get(int(segment.end_seq))
        if start_index is None or end_index is None or start_index > end_index:
            raise RuntimeError(f"Invalid segment bounds: {segment.start_seq}-{segment.end_seq}")

        # target_utterances 是当前段真正要 revise 的内容；前后文只帮助模型理解，不要求返回。
        target_utterances = utterances[start_index : end_index + 1]
        context_before = utterances[max(0, start_index - _SEGMENT_CONTEXT_UTTERANCE_COUNT) : start_index]
        context_after = utterances[end_index + 1 : end_index + 1 + _SEGMENT_CONTEXT_UTTERANCE_COUNT]

        request_name = f"segment_revision[{segment.segment_index}][{segment.start_seq}-{segment.end_seq}]"
        messages = self._build_segment_revision_messages(
            transcript_id=transcript_id,
            segment=segment,
            user_prompt=user_prompt,
            target_language=target_language,
            cue_language=cue_language,
            context_before=context_before,
            target_utterances=target_utterances,
            context_after=context_after,
        )
        utterance_by_seq = {int(item.utterance_seq): item for item in target_utterances}
        suggestions: list[RevisionSuggestion] = []
        seen_source_seqs: set[int] = set()
        buffer = ""
        line_count = 0
        first_item_logged = False
        started_perf = perf_counter()

        logger.info(
            "Revision segment stream parse started transcript_id=%s request_name=%s target_count=%s context_before=%s context_after=%s",
            transcript_id,
            request_name,
            len(target_utterances),
            len(context_before),
            len(context_after),
        )

        for delta in self._request_chat_completion_stream(
            transcript_id=transcript_id,
            request_name=request_name,
            messages=messages,
        ):
            buffer += delta
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                line_count += 1
                for suggestion in self._parse_revision_stream_line(line=line, utterance_by_seq=utterance_by_seq):
                    self._ensure_no_stream_overlap(suggestion=suggestion, seen_source_seqs=seen_source_seqs)
                    suggestions.append(suggestion)
                    if not first_item_logged:
                        first_item_logged = True
                        logger.info(
                            "Revision segment first valid item parsed transcript_id=%s request_name=%s elapsed_ms=%s lines=%s source_seqs=%s",
                            transcript_id,
                            request_name,
                            int((perf_counter() - started_perf) * 1000),
                            line_count,
                            suggestion.source_seqs,
                        )
                    yield suggestion

        if buffer.strip():
            line_count += 1
            for suggestion in self._parse_revision_stream_line(line=buffer, utterance_by_seq=utterance_by_seq):
                self._ensure_no_stream_overlap(suggestion=suggestion, seen_source_seqs=seen_source_seqs)
                suggestions.append(suggestion)
                if not first_item_logged:
                    first_item_logged = True
                    logger.info(
                        "Revision segment first valid item parsed transcript_id=%s request_name=%s elapsed_ms=%s lines=%s source_seqs=%s",
                        transcript_id,
                        request_name,
                        int((perf_counter() - started_perf) * 1000),
                        line_count,
                        suggestion.source_seqs,
                    )
                yield suggestion

        self._validate_revision_suggestions(suggestions=suggestions, utterances=target_utterances)
        logger.info(
            "Revision segment stream parse finished transcript_id=%s request_name=%s item_count=%s lines=%s elapsed_ms=%s",
            transcript_id,
            request_name,
            len(suggestions),
            line_count,
            int((perf_counter() - started_perf) * 1000),
        )

    def _request_chat_completion(
        self,
        *,
        transcript_id: str,
        request_name: str,
        messages: list[ChatCompletionMessageParam],
    ) -> str:
        client = self._get_client()
        started_at = datetime.now(timezone.utc)
        started_perf = perf_counter()
        logger.info(
            "LLM request started transcript_id=%s request_name=%s model=%s started_at=%s",
            transcript_id,
            request_name,
            self._model,
            started_at.isoformat(),
        )

        content: str | None = None
        error_message: str | None = None
        finish_reason: str | None = None
        try:
            response = client.chat.completions.create(
                model=self._model,
                temperature=0.2,
                messages=messages,
                timeout=self._timeout,
                reasoning_effort="minimal",
                # 火山的扩展参数放这里，disabled 对应关闭深度思考
                extra_body={
                    "thinking": {"type": "disabled"},
                },
            )
            if not response.choices:
                raise RuntimeError("LLM returned no choices")

            choice = response.choices[0]
            finish_reason = getattr(choice, "finish_reason", None)
            content = choice.message.content
            if content is None or not content.strip():
                raise RuntimeError("LLM returned empty content")
            if finish_reason not in (None, "stop"):
                raise RuntimeError(f"LLM stopped with finish_reason={finish_reason}")
            return content
        except Exception as exc:
            error_message = str(exc)
            raise
        finally:
            finished_at = datetime.now(timezone.utc)
            duration_ms = int((perf_counter() - started_perf) * 1000)
            self._append_debug_dump(
                transcript_id=transcript_id,
                request_name=request_name,
                messages=messages,
                started_at=started_at,
                finished_at=finished_at,
                duration_ms=duration_ms,
                response_content=content,
                error_message=error_message,
                finish_reason=finish_reason,
            )
            if error_message is None:
                logger.info(
                    "LLM request finished transcript_id=%s request_name=%s model=%s finished_at=%s duration_ms=%s",
                    transcript_id,
                    request_name,
                    self._model,
                    finished_at.isoformat(),
                    duration_ms,
                )
            else:
                logger.error(
                    "LLM request failed transcript_id=%s request_name=%s model=%s finished_at=%s duration_ms=%s error=%s",
                    transcript_id,
                    request_name,
                    self._model,
                    finished_at.isoformat(),
                    duration_ms,
                    error_message,
                )

    def _request_chat_completion_stream(
        self,
        *,
        transcript_id: str,
        request_name: str,
        messages: list[ChatCompletionMessageParam],
    ):
        client = self._get_client()
        started_at = datetime.now(timezone.utc)
        started_perf = perf_counter()
        logger.info(
            "LLM stream request started transcript_id=%s request_name=%s model=%s started_at=%s",
            transcript_id,
            request_name,
            self._model,
            started_at.isoformat(),
        )

        content_parts: list[str] = []
        error_message: str | None = None
        finish_reason: str | None = None
        chunk_count = 0
        content_chunk_count = 0
        first_chunk_logged = False
        first_content_logged = False
        try:
            stream = client.chat.completions.create(
                model=self._model,
                temperature=0.2,
                messages=messages,
                timeout=self._timeout,
                stream=True,
                reasoning_effort="minimal",
                # 火山的扩展参数放这里，disabled 对应关闭深度思考
                extra_body={
                    "thinking": {"type": "disabled"},
                },
            )
            logger.info(
                "LLM stream opened transcript_id=%s request_name=%s model=%s elapsed_ms=%s",
                transcript_id,
                request_name,
                self._model,
                int((perf_counter() - started_perf) * 1000),
            )

            for chunk in stream:
                chunk_count += 1
                if not first_chunk_logged:
                    first_chunk_logged = True
                    logger.info(
                        "LLM stream first chunk received transcript_id=%s request_name=%s model=%s elapsed_ms=%s",
                        transcript_id,
                        request_name,
                        self._model,
                        int((perf_counter() - started_perf) * 1000),
                    )
                if not chunk.choices:
                    continue

                choice = chunk.choices[0]
                chunk_finish_reason = getattr(choice, "finish_reason", None)
                if chunk_finish_reason is not None:
                    finish_reason = chunk_finish_reason

                delta = getattr(choice, "delta", None)
                content = getattr(delta, "content", None) if delta is not None else None
                if not content:
                    continue

                content_chunk_count += 1
                if not first_content_logged:
                    first_content_logged = True
                    logger.info(
                        "LLM stream first content chunk received transcript_id=%s request_name=%s model=%s elapsed_ms=%s chars=%s",
                        transcript_id,
                        request_name,
                        self._model,
                        int((perf_counter() - started_perf) * 1000),
                        len(content),
                    )

                content_parts.append(content)
                yield content

            if finish_reason not in (None, "stop"):
                raise RuntimeError(f"LLM stream stopped with finish_reason={finish_reason}")
        except Exception as exc:
            error_message = str(exc)
            raise
        finally:
            finished_at = datetime.now(timezone.utc)
            duration_ms = int((perf_counter() - started_perf) * 1000)
            self._append_debug_dump(
                transcript_id=transcript_id,
                request_name=request_name,
                messages=messages,
                started_at=started_at,
                finished_at=finished_at,
                duration_ms=duration_ms,
                response_content="".join(content_parts),
                error_message=error_message,
                finish_reason=finish_reason,
            )
            if error_message is None:
                logger.info(
                    "LLM stream finished transcript_id=%s request_name=%s model=%s duration_ms=%s chunks=%s content_chunks=%s chars=%s finish_reason=%s",
                    transcript_id,
                    request_name,
                    self._model,
                    duration_ms,
                    chunk_count,
                    content_chunk_count,
                    sum(len(part) for part in content_parts),
                    finish_reason or "",
                )
            else:
                logger.error(
                    "LLM stream failed transcript_id=%s request_name=%s model=%s duration_ms=%s chunks=%s content_chunks=%s error=%s",
                    transcript_id,
                    request_name,
                    self._model,
                    duration_ms,
                    chunk_count,
                    content_chunk_count,
                    error_message,
                )

    def _build_segment_plan_messages(
        self,
        *,
        transcript_id: str,
        utterances: list[RevisionPromptUtterance],
        user_prompt: str | None,
    ) -> list[ChatCompletionMessageParam]:
        payload = {
            "transcript_id": transcript_id,
            "user_prompt": (user_prompt or "").strip(),
            "utterances": [
                {
                    "utterance_seq": int(item.utterance_seq),
                    "speaker": item.speaker,
                    "text": item.text,
                }
                for item in utterances
            ],
        }
        user_content = (
            "Plan coherent revision segments for the following transcript.\n"
            "Input JSON:\n"
            f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
        )
        system_message: ChatCompletionSystemMessageParam = {
            "role": "system",
            "content": _SEGMENT_PLAN_SYSTEM_PROMPT,
        }
        user_message: ChatCompletionUserMessageParam = {
            "role": "user",
            "content": user_content,
        }
        return [system_message, user_message]

    def _build_segment_revision_messages(
        self,
        *,
        transcript_id: str,
        segment: RevisionSegment,
        user_prompt: str | None,
        target_language: str | None,
        cue_language: str | None,
        context_before: list[RevisionPromptUtterance],
        target_utterances: list[RevisionPromptUtterance],
        context_after: list[RevisionPromptUtterance],
    ) -> list[ChatCompletionMessageParam]:
        payload = {
            "transcript_id": transcript_id,
            "user_prompt": (user_prompt or "").strip(),
            "segment": {
                "segment_index": int(segment.segment_index),
                "start_seq": int(segment.start_seq),
                "end_seq": int(segment.end_seq),
                "title": segment.title,
                "summary": segment.summary,
            },
            "context_before": [self._serialize_prompt_utterance(item) for item in context_before],
            "target_utterances": [self._serialize_prompt_utterance(item) for item in target_utterances],
            "context_after": [self._serialize_prompt_utterance(item) for item in context_after],
        }
        user_content = (
            f"Revise the target utterances from the following spoken {_language_label(target_language)} transcript segment.\n"
            "Use the segment summary and nearby context only for understanding.\n"
            "Input JSON:\n"
            f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
        )
        system_message: ChatCompletionSystemMessageParam = {
            "role": "system",
            "content": _build_segment_revision_system_prompt(target_language, cue_language),
        }
        user_message: ChatCompletionUserMessageParam = {
            "role": "user",
            "content": user_content,
        }
        return [system_message, user_message]

    @staticmethod
    def _serialize_prompt_utterance(item: RevisionPromptUtterance) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "utterance_seq": int(item.utterance_seq),
            "speaker": item.speaker,
            "text": item.text,
        }
        if item.addions:
            payload["addions"] = item.addions
        return payload

    def _parse_segment_plan_response(
        self,
        *,
        content: str,
        utterances: list[RevisionPromptUtterance],
    ) -> list[RevisionSegment]:
        parsed = self._loads_json(content)
        raw_segments = self._extract_segments(parsed)
        if not raw_segments:
            raise RuntimeError("LLM returned no revision segments")

        segments: list[RevisionSegment] = []
        for index, raw_segment in enumerate(raw_segments, start=1):
            if not isinstance(raw_segment, dict):
                continue
            segment = self._normalize_segment(raw_segment=raw_segment, default_index=index)
            if segment is not None:
                segments.append(segment)

        if not segments:
            raise RuntimeError("LLM returned no valid revision segments")

        return self._validate_segment_plan(segments=segments, utterances=utterances)

    def _normalize_segment(
        self,
        *,
        raw_segment: dict[str, Any],
        default_index: int,
    ) -> RevisionSegment | None:
        start_seq = self._coerce_int(raw_segment.get("start_seq"))
        end_seq = self._coerce_int(raw_segment.get("end_seq"))
        if start_seq is None or end_seq is None or start_seq > end_seq:
            return None

        segment_index = self._coerce_int(raw_segment.get("segment_index")) or default_index
        title = self._normalize_brief_text(raw_segment.get("title"))
        summary = self._normalize_brief_text(raw_segment.get("summary"))
        return RevisionSegment(
            segment_index=int(segment_index),
            start_seq=int(start_seq),
            end_seq=int(end_seq),
            title=title,
            summary=summary,
        )

    def _validate_segment_plan(
        self,
        *,
        segments: list[RevisionSegment],
        utterances: list[RevisionPromptUtterance],
    ) -> list[RevisionSegment]:
        expected_seqs = [int(item.utterance_seq) for item in utterances]
        if not expected_seqs:
            return []

        normalized_segments = sorted(segments, key=lambda item: (int(item.start_seq), int(item.end_seq)))
        covered_seqs: list[int] = []
        final_segments: list[RevisionSegment] = []
        for index, segment in enumerate(normalized_segments, start=1):
            final_segments.append(
                RevisionSegment(
                    segment_index=index,
                    start_seq=int(segment.start_seq),
                    end_seq=int(segment.end_seq),
                    title=segment.title,
                    summary=segment.summary,
                )
            )
            covered_seqs.extend(range(int(segment.start_seq), int(segment.end_seq) + 1))

        if covered_seqs != expected_seqs:
            raise RuntimeError("LLM segment plan does not fully cover utterance_seq without gaps or overlaps")
        return final_segments

    def _parse_revision_response(
        self,
        *,
        content: str,
        utterances: list[RevisionPromptUtterance],
    ) -> list[RevisionSuggestion]:
        parsed = self._loads_json(content)
        raw_items = self._extract_items(parsed)
        if not raw_items:
            raise RuntimeError("LLM returned no revision items")

        utterance_by_seq = {int(item.utterance_seq): item for item in utterances}
        suggestions: list[RevisionSuggestion] = []
        for raw_item in raw_items:
            if not isinstance(raw_item, dict):
                continue
            suggestion = self._normalize_suggestion(raw_item=raw_item, utterance_by_seq=utterance_by_seq)
            if suggestion is not None:
                suggestions.append(suggestion)
        return self._validate_revision_suggestions(suggestions=suggestions, utterances=utterances)

    def _parse_revision_stream_line(
        self,
        *,
        line: str,
        utterance_by_seq: dict[int, RevisionPromptUtterance],
    ) -> list[RevisionSuggestion]:
        stripped = line.strip()
        if not stripped or stripped.startswith("```"):
            return []

        parsed = self._loads_json(stripped)
        raw_items = self._extract_items(parsed)
        if not raw_items and isinstance(parsed, dict):
            raw_items = [parsed]

        suggestions: list[RevisionSuggestion] = []
        for raw_item in raw_items:
            if not isinstance(raw_item, dict):
                continue
            suggestion = self._normalize_suggestion(raw_item=raw_item, utterance_by_seq=utterance_by_seq)
            if suggestion is not None:
                suggestions.append(suggestion)
        return suggestions

    def _normalize_suggestion(
        self,
        *,
        raw_item: dict[str, Any],
        utterance_by_seq: dict[int, RevisionPromptUtterance],
    ) -> RevisionSuggestion | None:
        source_seqs = self._normalize_source_seqs(raw_item=raw_item, utterance_by_seq=utterance_by_seq)
        if not source_seqs:
            return None

        source_seq_start = int(source_seqs[0])
        speakers = {
            (utterance_by_seq[int(seq)].speaker or "").strip()
            for seq in source_seqs
        }
        if len(speakers) > 1:
            raise RuntimeError(f"LLM merged utterances from different speakers in source_seqs={source_seqs}")

        issue_tags_list = self._normalize_string_list(raw_item.get("issue_tags"), max_items=_MAX_ISSUE_TAGS)
        explanations_text = self._normalize_explanations_text(raw_item.get("explanations"))
        score = self._require_score(raw_item.get("score"), utterance_seq=source_seq_start)

        return RevisionSuggestion(
            source_seqs=source_seqs,
            suggested_text=self._build_suggested_script(
                suggested_text=raw_item.get("suggested_text"),
                utterance_seq=source_seq_start,
            ),
            score=score,
            issue_tags=", ".join(issue_tags_list),
            explanations=explanations_text,
        )

    @staticmethod
    def _ensure_no_stream_overlap(
        *,
        suggestion: RevisionSuggestion,
        seen_source_seqs: set[int],
    ) -> None:
        source_seqs = {int(seq) for seq in suggestion.source_seqs}
        overlapping_source_seqs = sorted(source_seqs.intersection(seen_source_seqs))
        if overlapping_source_seqs:
            joined = ", ".join(str(seq) for seq in overlapping_source_seqs)
            raise RuntimeError(f"LLM stream returned overlapping source_seqs: {joined}")
        seen_source_seqs.update(source_seqs)

    def _get_client(self) -> OpenAI:
        if self._client is not None:
            return self._client
        if not self._api_key:
            raise RuntimeError("REVISION_LLM_API_KEY is not configured")
        if not self._base_url:
            raise RuntimeError("REVISION_LLM_BASE_URL is not configured")
        if not self._model:
            raise RuntimeError("REVISION_LLM_MODEL is not configured")

        http_client = httpx.Client(timeout=self._timeout, trust_env=False)
        self._client = OpenAI(
            api_key=self._api_key,
            base_url=self._base_url,
            http_client=http_client,
        )
        return self._client

    def _append_debug_dump(
        self,
        *,
        transcript_id: str,
        request_name: str,
        messages: list[ChatCompletionMessageParam],
        started_at: datetime,
        finished_at: datetime,
        duration_ms: int,
        response_content: str | None,
        error_message: str | None,
        finish_reason: str | None,
    ) -> None:
        if not self._debug_file:
            return

        debug_path = Path(self._debug_file).expanduser()
        debug_path.parent.mkdir(parents=True, exist_ok=True)
        dump_lines = [
            "===== LLM Revision Request =====",
            f"request_name: {request_name}",
            f"transcript_id: {transcript_id}",
            f"model: {self._model}",
            f"started_at: {started_at.isoformat()}",
            f"finished_at: {finished_at.isoformat()}",
            f"duration_ms: {duration_ms}",
            f"finish_reason: {finish_reason or ''}",
            "",
            "[messages]",
            json.dumps(messages, ensure_ascii=False, indent=2),
            "",
            "[response]",
            response_content or "",
        ]
        if error_message:
            dump_lines.extend(
                [
                    "",
                    "[error]",
                    error_message,
                ]
            )
        dump_lines.extend(["", ""])
        try:
            with debug_path.open("a", encoding="utf-8") as file:
                file.write("\n".join(dump_lines))
        except OSError as exc:
            logger.warning("Failed to write LLM revision debug dump %s: %s", debug_path, exc)

    @staticmethod
    def _normalize_explanations_text(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return re.sub(r"\s+", " ", value).strip()
        if isinstance(value, list):
            parts = [re.sub(r"\s+", " ", str(item)).strip() for item in value if str(item).strip()]
            return " ".join(parts)
        return re.sub(r"\s+", " ", str(value)).strip()

    @staticmethod
    def _normalize_brief_text(value: Any) -> str:
        if value is None:
            return ""
        return re.sub(r"\s+", " ", str(value)).strip()

    @staticmethod
    def _deduplicate_suggestions(suggestions: list[RevisionSuggestion]) -> list[RevisionSuggestion]:
        deduplicated: list[RevisionSuggestion] = []
        seen_spans: set[tuple[int, ...]] = set()
        for suggestion in sorted(
            suggestions,
            key=lambda item: (
                int(item.source_seqs[0]),
                int(item.source_seqs[-1]),
            ),
        ):
            span_key = tuple(int(seq) for seq in suggestion.source_seqs)
            if span_key in seen_spans:
                continue
            deduplicated.append(suggestion)
            seen_spans.add(span_key)
        return deduplicated

    @staticmethod
    def _normalize_source_seqs(
        *,
        raw_item: dict[str, Any],
        utterance_by_seq: dict[int, RevisionPromptUtterance],
    ) -> list[int]:
        raw_source_seqs = raw_item.get("source_seqs")
        if isinstance(raw_source_seqs, list):
            normalized_source_seqs: list[int] = []
            seen_seqs: set[int] = set()
            for raw_source_seq in raw_source_seqs:
                source_seq = LLMRevisionGenerator._coerce_int(raw_source_seq)
                if source_seq is None or source_seq not in utterance_by_seq or source_seq in seen_seqs:
                    return []
                normalized_source_seqs.append(int(source_seq))
                seen_seqs.add(int(source_seq))
            ordered_source_seqs = sorted(normalized_source_seqs)
            if not ordered_source_seqs:
                return []
            expected_source_seqs = list(range(ordered_source_seqs[0], ordered_source_seqs[-1] + 1))
            if ordered_source_seqs != expected_source_seqs:
                return []
            return ordered_source_seqs

        utterance_seq = LLMRevisionGenerator._coerce_int(raw_item.get("utterance_seq"))
        if utterance_seq is None or utterance_seq not in utterance_by_seq:
            return []
        return [int(utterance_seq)]

    @staticmethod
    def _validate_revision_suggestions(
        *,
        suggestions: list[RevisionSuggestion],
        utterances: list[RevisionPromptUtterance],
    ) -> list[RevisionSuggestion]:
        expected_seqs = [int(item.utterance_seq) for item in utterances]
        if not suggestions:
            raise RuntimeError("LLM returned no valid revision items")

        normalized_suggestions = sorted(
            suggestions,
            key=lambda item: (
                int(item.source_seqs[0]),
                int(item.source_seqs[-1]),
            ),
        )
        covered_seqs: list[int] = []
        for suggestion in normalized_suggestions:
            covered_seqs.extend(int(seq) for seq in suggestion.source_seqs)

        if covered_seqs != expected_seqs:
            raise RuntimeError("LLM revision items do not fully cover target utterance_seq without gaps or overlaps")
        return normalized_suggestions

    @staticmethod
    def _loads_json(content: str) -> Any:
        candidates: list[str] = []
        initial_candidate = content.strip()
        if initial_candidate:
            candidates.append(initial_candidate)

        fenced_match = _CODE_FENCE_JSON_RE.search(content)
        if fenced_match is not None:
            fenced_candidate = fenced_match.group(1).strip()
            if fenced_candidate:
                candidates.append(fenced_candidate)

        start = min((index for index in (content.find("{"), content.find("[")) if index >= 0), default=-1)
        if start >= 0:
            for open_char, close_char in (("{", "}"), ("[", "]")):
                open_index = content.find(open_char, start)
                close_index = content.rfind(close_char)
                if open_index >= 0 and close_index > open_index:
                    extracted_candidate = content[open_index : close_index + 1].strip()
                    if extracted_candidate:
                        candidates.append(extracted_candidate)

        if not candidates:
            raise RuntimeError("Unable to locate JSON in LLM response")

        last_error: Exception | None = None
        seen_candidates: set[str] = set()
        for candidate in candidates:
            if candidate in seen_candidates:
                continue
            seen_candidates.add(candidate)
            try:
                return json.loads(candidate)
            except json.JSONDecodeError as exc:
                last_error = exc

            try:
                return repair_json(candidate, return_objects=True, skip_json_loads=True)
            except Exception as exc:  # pragma: no cover
                last_error = exc

        if last_error is not None:
            message = getattr(last_error, "msg", str(last_error)) or "unknown parse error"
            raise RuntimeError(f"Unable to parse JSON from LLM response: {message}")
        raise RuntimeError("Unable to parse JSON from LLM response")

    @staticmethod
    def _extract_items(payload: Any) -> list[Any]:
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            items = payload.get("items")
            if isinstance(items, list):
                return items
        return []

    @staticmethod
    def _extract_segments(payload: Any) -> list[Any]:
        if isinstance(payload, dict):
            segments = payload.get("segments")
            if isinstance(segments, list):
                return segments
        return []

    @staticmethod
    def _coerce_int(value: Any) -> int | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return None
            try:
                return int(float(stripped))
            except ValueError:
                return None
        return None

    @staticmethod
    def _require_text(value: Any, *, field_name: str, utterance_seq: int) -> str:
        text = re.sub(r"\s+", " ", str(value).strip()) if value is not None else ""
        if text:
            return text
        raise RuntimeError(f"LLM response missing {field_name} for utterance_seq={utterance_seq}")

    @staticmethod
    def _build_suggested_script(*, suggested_text: Any, utterance_seq: int) -> str:
        return LLMRevisionGenerator._require_text(
            suggested_text,
            field_name="suggested_text",
            utterance_seq=utterance_seq,
        )

    @staticmethod
    def _normalize_string_list(value: Any, *, max_items: int) -> list[str]:
        raw_items: list[str] = []
        if isinstance(value, str):
            raw_items = [part.strip() for part in _SPLIT_TEXT_RE.split(value)]
        elif isinstance(value, list):
            raw_items = [str(part).strip() for part in value]

        normalized: list[str] = []
        seen: set[str] = set()
        for item in raw_items:
            if not item:
                continue
            compact = re.sub(r"\s+", " ", item).strip()
            if not compact or compact in seen:
                continue
            normalized.append(compact)
            seen.add(compact)
            if len(normalized) >= max_items:
                break
        return normalized

    @staticmethod
    def _require_score(value: Any, *, utterance_seq: int) -> int:
        score = LLMRevisionGenerator._coerce_int(value)
        if score is None:
            raise RuntimeError(f"LLM response missing score for utterance_seq={utterance_seq}")
        if score < 0 or score > 100:
            raise RuntimeError(f"LLM response score out of range for utterance_seq={utterance_seq}: {score}")
        return int(score)


def _build_segment_revision_system_prompt(target_language: str | None, cue_language: str | None) -> str:
    spoken_language = _language_label(target_language)
    cue_language_label = _language_label(cue_language or target_language)
    cue_example = (
        "用轻松自然的语气开口"
        if _is_chinese_language(cue_language or target_language)
        else "Open with relaxed, natural curiosity"
    )
    text_example = "你上周末做了什么？" if _is_chinese_language(target_language) else "What did you do last weekend?"
    example = f"[{cue_example}] {text_example}"
    return (
        _SEGMENT_REVISION_SYSTEM_PROMPT_TEMPLATE
        .replace("{spoken_language}", spoken_language)
        .replace("{cue_language}", cue_language_label)
        .replace("{suggested_text_example}", example)
    )


def _is_chinese_language(value: str | None) -> bool:
    return (value or "").strip().lower().startswith("zh")


def _language_label(value: str | None) -> str:
    normalized = (value or "en").strip().lower()
    if normalized.startswith("zh"):
        return "Simplified Chinese"
    if normalized.startswith("en"):
        return "English"
    return value.strip() if value and value.strip() else "English"
