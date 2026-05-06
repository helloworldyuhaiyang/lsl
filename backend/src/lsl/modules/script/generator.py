from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Iterator
from typing import Any

from json_repair import repair_json
from openai import OpenAI

from lsl.core.config import Settings
from lsl.modules.script.types import GeneratedScript, GeneratedScriptTurn, ScriptGenerateRequest, ScriptGenerator, ScriptSection

logger = logging.getLogger(__name__)

_CUE_BRACKETS_PATTERN = re.compile(r"^\[?(.*?)\]?$")
_SECTION_TARGET_TURNS = 12


def create_script_generator(settings: Settings) -> ScriptGenerator:
    provider = (settings.SCRIPT_PROVIDER or "").strip().lower()
    if provider == "fake":
        return FakeScriptGenerator()
    if provider == "llm":
        return LlmScriptGenerator(settings=settings)
    raise RuntimeError(f"Unsupported SCRIPT_PROVIDER: {settings.SCRIPT_PROVIDER!r}")


class FakeScriptGenerator:
    provider_name = "fake"

    def generate(self, req: ScriptGenerateRequest) -> GeneratedScript:
        speakers = [f"user-{index + 1}" for index in range(req.speaker_count)]
        if _is_chinese_language(req.target_language):
            base_texts = [
                "嘿，你现在方便吗？",
                "当然，你需要什么？",
                "我想在会议前练一下这段对话。",
                "没问题，我们先完整走一遍。",
                "我也希望听起来自然又自信。",
                "那就保持简短，说清楚重点。",
                "有道理，我再试一次。",
                "来吧，我在听。",
            ]
        else:
            base_texts = [
                "Hey, do you have a minute?",
                "Sure. What do you need?",
                "I want to practice this conversation before the meeting.",
                "No problem. Let's run through it once.",
                "I also want it to sound natural and confident.",
                "Then keep it short and say it clearly.",
                "That makes sense. Let me try again.",
                "Go ahead. I'm listening.",
            ]
        if _is_chinese_language(req.cue_language or req.target_language):
            base_cues = [
                "轻松自然地开口",
                "随意但友好地回应",
                "带点认真地说明来意",
                "平稳地配合对方",
                "略带期待地补充",
                "平静地给建议",
                "重新组织后更自信地说",
                "简短地鼓励对方继续",
            ]
        else:
            base_cues = [
                "Open in a relaxed, natural tone",
                "Reply casually but warmly",
                "Explain the purpose with a focused tone",
                "Cooperate in a steady tone",
                "Add the thought with mild anticipation",
                "Give calm, practical advice",
                "Speak again with clearer confidence",
                "Encourage the other person to continue briefly",
            ]
        utterances: list[GeneratedScriptTurn] = []
        for index in range(req.turn_count):
            speaker = speakers[index % len(speakers)]
            utterances.append(
                GeneratedScriptTurn(
                    speaker=speaker,
                    cue=base_cues[index % len(base_cues)],
                    text=base_texts[index % len(base_texts)],
                )
            )
        return GeneratedScript(utterances=utterances)

    def generate_progressively(self, req: ScriptGenerateRequest) -> Iterator[GeneratedScriptTurn]:
        yield from self.generate(req).utterances

    def plan_sections(self, req: ScriptGenerateRequest) -> list[ScriptSection]:
        return _build_default_sections(req.turn_count)

    def generate_from_plan_progressively(
        self,
        req: ScriptGenerateRequest,
        sections: list[ScriptSection],
    ) -> Iterator[GeneratedScriptTurn]:
        yield from self.generate(req).utterances


class LlmScriptGenerator:
    provider_name = "llm"

    def __init__(self, *, settings: Settings) -> None:
        self._api_key = settings.SCRIPT_LLM_API_KEY
        self._base_url = settings.SCRIPT_LLM_BASE_URL
        self._model = settings.SCRIPT_LLM_MODEL
        self._timeout = float(settings.SCRIPT_LLM_HTTP_TIMEOUT)
        self._client: OpenAI | None = None

    def generate(self, req: ScriptGenerateRequest) -> GeneratedScript:
        speaker_names = [f"user-{index + 1}" for index in range(req.speaker_count)]
        response = self._get_client().chat.completions.create(
            model=self._model,
            temperature=0.9,
            messages=self._build_messages(req=req, speaker_names=speaker_names),
        )
        content = response.choices[0].message.content or ""
        parsed = self._parse_response_content(content=content)
        return self._normalize_generated_script(raw=parsed, speaker_names=speaker_names, req=req)

    def generate_progressively(self, req: ScriptGenerateRequest) -> Iterator[GeneratedScriptTurn]:
        started_at = time.monotonic()
        speaker_names = [f"user-{index + 1}" for index in range(req.speaker_count)]
        yielded = False
        try:
            for turn in self._stream_generated_turns(req=req, speaker_names=speaker_names):
                yielded = True
                yield turn
        except Exception:
            if yielded:
                raise
            logger.warning(
                "Script generator streaming failed before any turn; falling back to non-streaming request model=%s elapsed_ms=%s",
                self._model,
                int((time.monotonic() - started_at) * 1000),
                exc_info=True,
            )
            yield from self.generate(req).utterances

    def plan_sections(self, req: ScriptGenerateRequest) -> list[ScriptSection]:
        if req.turn_count <= 16:
            return []

        started_at = time.monotonic()
        speaker_names = [f"user-{index + 1}" for index in range(req.speaker_count)]
        logger.info(
            "Script section plan request started model=%s turn_count=%s speaker_count=%s prompt_len=%s",
            self._model,
            req.turn_count,
            req.speaker_count,
            len(req.prompt),
        )
        try:
            response = self._get_client().chat.completions.create(
                model=self._model,
                temperature=0.4,
                messages=self._build_section_plan_messages(req=req, speaker_names=speaker_names),
                timeout=self._timeout,
                reasoning_effort="minimal",
                extra_body={
                    "thinking": {"type": "disabled"},
                },
            )
            content = response.choices[0].message.content or ""
            sections = self._normalize_sections(raw=self._parse_response_content(content=content), turn_count=req.turn_count)
            logger.info(
                "Script section plan finished model=%s sections=%s elapsed_ms=%s",
                self._model,
                len(sections),
                int((time.monotonic() - started_at) * 1000),
            )
            return sections
        except Exception:
            logger.warning(
                "Script section plan failed; falling back to default sections model=%s elapsed_ms=%s",
                self._model,
                int((time.monotonic() - started_at) * 1000),
                exc_info=True,
            )
            return _build_default_sections(req.turn_count)

    def generate_from_plan_progressively(
        self,
        req: ScriptGenerateRequest,
        sections: list[ScriptSection],
    ) -> Iterator[GeneratedScriptTurn]:
        speaker_names = [f"user-{index + 1}" for index in range(req.speaker_count)]
        generated_turns: list[GeneratedScriptTurn] = []
        for section in sections:
            logger.info(
                "Script section generation started model=%s section_index=%s target_turn_count=%s generated_so_far=%s",
                self._model,
                section.section_index,
                section.target_turn_count,
                len(generated_turns),
            )
            section_count = 0
            messages = self._build_section_stream_messages(
                req=req,
                speaker_names=speaker_names,
                section=section,
                previous_turns=generated_turns[-6:],
                generated_turn_count=len(generated_turns),
            )
            for turn in self._stream_generated_turns(
                req=req,
                speaker_names=speaker_names,
                messages=messages,
                target_turn_count=section.target_turn_count,
                start_index=len(generated_turns),
                request_name=f"script_section[{section.section_index}]",
            ):
                generated_turns.append(turn)
                section_count += 1
                yield turn
                if section_count >= section.target_turn_count or len(generated_turns) >= req.turn_count:
                    break
            logger.info(
                "Script section generation finished model=%s section_index=%s turns=%s generated_total=%s",
                self._model,
                section.section_index,
                section_count,
                len(generated_turns),
            )
            if len(generated_turns) >= req.turn_count:
                return

    def _build_messages(self, *, req: ScriptGenerateRequest, speaker_names: list[str]) -> list[dict[str, str]]:
        language_label = _language_label(req.target_language)
        cue_language_label = _language_label(req.cue_language or req.target_language)
        cue_example = _cue_example(req.cue_language or req.target_language)
        text_example = _text_example(req.target_language)
        system_prompt = (
            f"You create cue-driven {language_label} speaking practice scripts.\n"
            "Return JSON only.\n"
            "Output schema:\n"
            "{\n"
            '  "utterances": [\n'
            f'    {{"speaker": "user-1", "cue": "{cue_example}", "text": "{text_example}"}}\n'
            "  ]\n"
            "}\n"
            "Rules:\n"
            f"- Use only these speakers: {', '.join(speaker_names)}.\n"
            f"- Target about {req.turn_count} utterances.\n"
            f"- Every utterance must include a non-empty cue and a non-empty spoken {language_label} text.\n"
            f"- cue must be concise {cue_language_label} guidance describing delivery, tone, emotion, rhythm, or subtext.\n"
            "- Do not include square brackets in the cue field.\n"
            f"- text must be spoken {language_label} only and must not include cue markers.\n"
            "- Keep the dialogue natural, practical, and suitable for TTS playback.\n"
            "- Alternate speakers naturally.\n"
            "- 适当的增加 Hmm,Well..., Let me think… , uh... , so, basically, actually, but, however, while 等使其更加逼真。"
        )
        user_payload = {
            "title": req.title,
            "description": req.description,
            "target_language": req.target_language,
            "cue_language": req.cue_language,
            "prompt": req.prompt,
            "turn_count": req.turn_count,
            "speaker_count": req.speaker_count,
            "difficulty": req.difficulty,
            "cue_style": req.cue_style,
            "must_include": req.must_include,
            "speakers": speaker_names,
        }
        return [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    "Generate a cue-first speaking practice script from the following request.\n"
                    "Return JSON only.\n"
                    f"{json.dumps(user_payload, ensure_ascii=False)}"
                ),
            },
        ]

    def _build_stream_messages(self, *, req: ScriptGenerateRequest, speaker_names: list[str]) -> list[dict[str, str]]:
        language_label = _language_label(req.target_language)
        cue_language_label = _language_label(req.cue_language or req.target_language)
        cue_example = _cue_example(req.cue_language or req.target_language)
        text_example = _text_example(req.target_language)
        system_prompt = (
            f"You create cue-driven {language_label} speaking practice scripts.\n"
            "Return newline-delimited JSON only. Do not wrap the response in markdown.\n"
            "Each line must be one complete JSON object with this schema:\n"
            f'{{"speaker":"user-1","cue":"{cue_example}","text":"{text_example}"}}\n'
            "Rules:\n"
            f"- Use only these speakers: {', '.join(speaker_names)}.\n"
            f"- Return exactly {req.turn_count} lines.\n"
            f"- Every line must include a non-empty cue and a non-empty spoken {language_label} text.\n"
            f"- cue must be concise {cue_language_label} guidance describing delivery, tone, emotion, rhythm, or subtext.\n"
            "- Do not include square brackets in the cue field.\n"
            f"- text must be spoken {language_label} only and must not include cue markers.\n"
            "- Keep the dialogue natural, practical, and suitable for TTS playback.\n"
            "- Alternate speakers naturally.\n"
            "- 适当的增加 Hmm,Well..., Let me think… , uh... , so, basically, actually, but, however, while 等使其更加逼真。"
        )
        user_payload = {
            "title": req.title,
            "description": req.description,
            "target_language": req.target_language,
            "cue_language": req.cue_language,
            "prompt": req.prompt,
            "turn_count": req.turn_count,
            "speaker_count": req.speaker_count,
            "difficulty": req.difficulty,
            "cue_style": req.cue_style,
            "must_include": req.must_include,
            "speakers": speaker_names,
        }
        return [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    "Generate a cue-first speaking practice script from the following request.\n"
                    "Return NDJSON only: one complete JSON object per line.\n"
                    f"{json.dumps(user_payload, ensure_ascii=False)}"
                ),
            },
        ]

    def _build_section_plan_messages(self, *, req: ScriptGenerateRequest, speaker_names: list[str]) -> list[dict[str, str]]:
        language_label = _language_label(req.target_language)
        user_payload = {
            "title": req.title,
            "description": req.description,
            "target_language": req.target_language,
            "cue_language": req.cue_language,
            "prompt": req.prompt,
            "turn_count": req.turn_count,
            "speaker_count": req.speaker_count,
            "difficulty": req.difficulty,
            "cue_style": req.cue_style,
            "must_include": req.must_include,
            "speakers": speaker_names,
        }
        system_prompt = (
            f"You plan a cue-driven {language_label} speaking practice dialogue before generation.\n"
            "Return JSON only.\n"
            "Output schema:\n"
            "{\n"
            '  "sections": [\n'
            '    {"section_index": 1, "title": "Opening", "summary": "Set up the scene and establish the speakers.", "target_turn_count": 8}\n'
            "  ]\n"
            "}\n"
            "Rules:\n"
            f"- The sum of target_turn_count must equal exactly {req.turn_count}.\n"
            "- Use 2 to 4 sections.\n"
            "- Each section should contain about 6 to 12 turns.\n"
            "- Keep sections in chronological order.\n"
            "- Make titles short and user-facing.\n"
            "- Summaries should describe what the section should accomplish, not the exact script lines.\n"
            "- Do not generate dialogue turns yet.\n"
        )
        return [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    "Plan sections for this AI script request.\n"
                    "Return JSON only.\n"
                    f"{json.dumps(user_payload, ensure_ascii=False)}"
                ),
            },
        ]

    def _build_section_stream_messages(
        self,
        *,
        req: ScriptGenerateRequest,
        speaker_names: list[str],
        section: ScriptSection,
        previous_turns: list[GeneratedScriptTurn],
        generated_turn_count: int,
    ) -> list[dict[str, str]]:
        language_label = _language_label(req.target_language)
        cue_language_label = _language_label(req.cue_language or req.target_language)
        cue_example = _cue_example(req.cue_language or req.target_language)
        text_example = _text_example(req.target_language)
        previous_payload = [
            {
                "speaker": item.speaker,
                "cue": item.cue,
                "text": item.text,
            }
            for item in previous_turns
        ]
        system_prompt = (
            f"You create one section of a cue-driven {language_label} speaking practice script.\n"
            "Return newline-delimited JSON only. Do not wrap the response in markdown.\n"
            "Each line must be one complete JSON object with this schema:\n"
            f'{{"speaker":"user-1","cue":"{cue_example}","text":"{text_example}"}}\n'
            "Rules:\n"
            f"- Use only these speakers: {', '.join(speaker_names)}.\n"
            f"- Return exactly {section.target_turn_count} lines for this section.\n"
            f"- This is section {section.section_index}: {section.title}.\n"
            f"- Section goal: {section.summary}.\n"
            f"- The full script target is {req.turn_count} turns; {generated_turn_count} turns have already been generated before this section.\n"
            f"- Every line must include a non-empty cue and a non-empty spoken {language_label} text.\n"
            f"- cue must be concise {cue_language_label} guidance describing delivery, tone, emotion, rhythm, or subtext.\n"
            "- Do not include square brackets in the cue field.\n"
            f"- text must be spoken {language_label} only and must not include cue markers.\n"
            "- Continue naturally from previous_turns. Avoid repeating setup already covered.\n"
            "- Keep the dialogue natural, practical, and suitable for TTS playback.\n"
            "- Alternate speakers naturally.\n"
            "- 适当的增加 Hmm,Well..., Let me think… , uh... , so, basically, actually, but, however, while 等使其更加逼真。"
        )
        user_payload = {
            "title": req.title,
            "description": req.description,
            "target_language": req.target_language,
            "cue_language": req.cue_language,
            "prompt": req.prompt,
            "turn_count": req.turn_count,
            "speaker_count": req.speaker_count,
            "difficulty": req.difficulty,
            "cue_style": req.cue_style,
            "must_include": req.must_include,
            "speakers": speaker_names,
            "section": {
                "section_index": section.section_index,
                "title": section.title,
                "summary": section.summary,
                "target_turn_count": section.target_turn_count,
            },
            "previous_turns": previous_payload,
        }
        return [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    "Generate this section of the script.\n"
                    "Return NDJSON only: one complete JSON object per line.\n"
                    f"{json.dumps(user_payload, ensure_ascii=False)}"
                ),
            },
        ]

    def _stream_generated_turns(
        self,
        *,
        req: ScriptGenerateRequest,
        speaker_names: list[str],
        messages: list[dict[str, str]] | None = None,
        target_turn_count: int | None = None,
        start_index: int = 0,
        request_name: str = "script",
    ) -> Iterator[GeneratedScriptTurn]:
        started_at = time.monotonic()
        target_count = int(target_turn_count or req.turn_count)
        logger.info(
            "Script LLM stream request started model=%s request_name=%s turn_count=%s speaker_count=%s prompt_len=%s",
            self._model,
            request_name,
            target_count,
            req.speaker_count,
            len(req.prompt),
        )
        stream = self._get_client().chat.completions.create(
            model=self._model,
            temperature=0.9,
            messages=messages or self._build_stream_messages(req=req, speaker_names=speaker_names),
            stream=True,
            # 火山的扩展参数放这里，disabled 对应关闭深度思考
            extra_body={
                "thinking": {"type": "disabled"},
            },
        )
        logger.info(
            "Script LLM stream opened model=%s request_name=%s elapsed_ms=%s",
            self._model,
            request_name,
            int((time.monotonic() - started_at) * 1000),
        )
        buffer = ""
        full_content_parts: list[str] = []
        yielded_count = 0
        chunk_count = 0
        non_empty_chunk_count = 0
        line_count = 0
        first_chunk_logged = False
        first_non_empty_chunk_logged = False
        first_turn_logged = False

        for chunk in stream:
            chunk_count += 1
            if not first_chunk_logged:
                first_chunk_logged = True
                logger.info(
                    "Script LLM stream first chunk received model=%s request_name=%s elapsed_ms=%s",
                    self._model,
                    request_name,
                    int((time.monotonic() - started_at) * 1000),
                )
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content or ""
            if not delta:
                continue
            non_empty_chunk_count += 1
            if not first_non_empty_chunk_logged:
                first_non_empty_chunk_logged = True
                logger.info(
                    "Script LLM stream first content chunk received model=%s request_name=%s elapsed_ms=%s chars=%s",
                    self._model,
                    request_name,
                    int((time.monotonic() - started_at) * 1000),
                    len(delta),
                )

            full_content_parts.append(delta)
            buffer += delta
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                line_count += 1
                turn = self._parse_stream_line(line=line, speaker_names=speaker_names, index=start_index + yielded_count)
                if turn is None:
                    continue
                if not first_turn_logged:
                    first_turn_logged = True
                    logger.info(
                        "Script LLM stream first valid turn parsed model=%s request_name=%s elapsed_ms=%s chunks=%s lines=%s buffered_chars=%s",
                        self._model,
                        request_name,
                        int((time.monotonic() - started_at) * 1000),
                        non_empty_chunk_count,
                        line_count,
                        len(buffer),
                    )
                yield turn
                yielded_count += 1
                if yielded_count >= target_count:
                    logger.info(
                        "Script LLM stream stopped after target turns model=%s request_name=%s turns=%s chunks=%s lines=%s elapsed_ms=%s",
                        self._model,
                        request_name,
                        yielded_count,
                        non_empty_chunk_count,
                        line_count,
                        int((time.monotonic() - started_at) * 1000),
                    )
                    return

        turn = self._parse_stream_line(line=buffer, speaker_names=speaker_names, index=start_index + yielded_count)
        if turn is not None and yielded_count < target_count:
            if not first_turn_logged:
                logger.info(
                    "Script LLM stream first valid turn parsed at stream end model=%s request_name=%s elapsed_ms=%s chunks=%s lines=%s buffered_chars=%s",
                    self._model,
                    request_name,
                    int((time.monotonic() - started_at) * 1000),
                    non_empty_chunk_count,
                    line_count,
                    len(buffer),
                )
            yield turn
            yielded_count += 1

        if yielded_count > 0:
            logger.info(
                "Script LLM stream finished with parsed turns model=%s request_name=%s turns=%s chunks=%s raw_chunks=%s lines=%s total_chars=%s elapsed_ms=%s",
                self._model,
                request_name,
                yielded_count,
                non_empty_chunk_count,
                chunk_count,
                line_count,
                sum(len(part) for part in full_content_parts),
                int((time.monotonic() - started_at) * 1000),
            )
            return

        logger.warning(
            "Script LLM stream ended without valid NDJSON turns; attempting full response parse model=%s request_name=%s chunks=%s raw_chunks=%s lines=%s total_chars=%s elapsed_ms=%s",
            self._model,
            request_name,
            non_empty_chunk_count,
            chunk_count,
            line_count,
            sum(len(part) for part in full_content_parts),
            int((time.monotonic() - started_at) * 1000),
        )
        parsed = self._parse_response_content(content="".join(full_content_parts))
        for turn in self._normalize_generated_script(raw=parsed, speaker_names=speaker_names, req=req).utterances[:target_count]:
            yield turn
            yielded_count += 1
        logger.info(
            "Script LLM stream full response parse yielded turns model=%s request_name=%s turns=%s elapsed_ms=%s",
            self._model,
            request_name,
            yielded_count,
            int((time.monotonic() - started_at) * 1000),
        )

    def _normalize_sections(self, *, raw: dict[str, Any], turn_count: int) -> list[ScriptSection]:
        raw_sections = raw.get("sections")
        if not isinstance(raw_sections, list):
            return _build_default_sections(turn_count)

        sections: list[ScriptSection] = []
        remaining_turns = int(turn_count)
        for index, raw_section in enumerate(raw_sections, start=1):
            if not isinstance(raw_section, dict):
                continue
            target_turn_count = _coerce_positive_int(raw_section.get("target_turn_count"))
            if target_turn_count is None:
                continue
            title = _normalize_text(raw_section.get("title")) or f"Section {index}"
            summary = _normalize_text(raw_section.get("summary"))
            if remaining_turns <= 0:
                break
            normalized_count = min(target_turn_count, remaining_turns)
            sections.append(
                ScriptSection(
                    section_index=len(sections) + 1,
                    title=title,
                    summary=summary,
                    target_turn_count=normalized_count,
                )
            )
            remaining_turns -= normalized_count

        if not sections or remaining_turns != 0:
            return _build_default_sections(turn_count)
        return sections

    def _normalize_generated_script(
        self,
        *,
        raw: dict[str, Any],
        speaker_names: list[str],
        req: ScriptGenerateRequest,
    ) -> GeneratedScript:
        raw_utterances = raw.get("utterances")
        if not isinstance(raw_utterances, list) or not raw_utterances:
            raise RuntimeError("Script generator returned no utterances")

        normalized: list[GeneratedScriptTurn] = []
        for index, raw_item in enumerate(raw_utterances):
            if not isinstance(raw_item, dict):
                continue

            raw_speaker = str(raw_item.get("speaker") or "").strip()
            speaker = raw_speaker if raw_speaker in speaker_names else speaker_names[index % len(speaker_names)]

            cue_candidate = _normalize_text(raw_item.get("cue"))
            text_candidate = _normalize_text(raw_item.get("text"))
            if text_candidate.startswith("[") and "]" in text_candidate:
                text_candidate = text_candidate.split("]", 1)[1].strip()

            cue = _strip_cue_brackets(cue_candidate)
            text = text_candidate
            if not cue or not text:
                continue

            normalized.append(
                GeneratedScriptTurn(
                    speaker=speaker,
                    cue=cue,
                    text=text,
                )
            )

        if len(normalized) < 2:
            raise RuntimeError("Script generator returned too few valid utterances")

        if len(normalized) > req.turn_count:
            normalized = normalized[: req.turn_count]

        return GeneratedScript(utterances=normalized)

    def _parse_response_content(self, *, content: str) -> dict[str, Any]:
        candidate = content.strip()
        if not candidate:
            raise RuntimeError("Script generator returned empty content")
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            try:
                repaired = repair_json(candidate, return_objects=True, skip_json_loads=True)
            except Exception as exc:  # pragma: no cover
                logger.warning("Failed to repair script generator JSON: %s", exc)
                raise RuntimeError("Script generator returned invalid JSON") from exc
            if not isinstance(repaired, dict):
                raise RuntimeError("Script generator returned non-object JSON")
            return repaired
        if not isinstance(parsed, dict):
            raise RuntimeError("Script generator returned non-object JSON")
        return parsed

    def _parse_stream_line(
        self,
        *,
        line: str,
        speaker_names: list[str],
        index: int,
    ) -> GeneratedScriptTurn | None:
        candidate = line.strip()
        if not candidate or candidate.startswith("```"):
            return None
        if not candidate.startswith("{"):
            return None
        try:
            raw_item = json.loads(candidate)
        except json.JSONDecodeError:
            try:
                raw_item = repair_json(candidate, return_objects=True, skip_json_loads=True)
            except Exception:
                logger.debug("Skipping incomplete script stream line: %s", candidate)
                return None
        if not isinstance(raw_item, dict):
            return None

        raw_speaker = str(raw_item.get("speaker") or "").strip()
        speaker = raw_speaker if raw_speaker in speaker_names else speaker_names[index % len(speaker_names)]
        cue = _strip_cue_brackets(_normalize_text(raw_item.get("cue")))
        text = _normalize_text(raw_item.get("text"))
        if text.startswith("[") and "]" in text:
            text = text.split("]", 1)[1].strip()
        if not cue or not text:
            return None
        return GeneratedScriptTurn(speaker=speaker, cue=cue, text=text)

    def _get_client(self) -> OpenAI:
        if self._client is not None:
            return self._client
        if not self._api_key:
            raise RuntimeError("SCRIPT_LLM_API_KEY is not configured")
        if not self._base_url:
            raise RuntimeError("SCRIPT_LLM_BASE_URL is not configured")
        if not self._model:
            raise RuntimeError("SCRIPT_LLM_MODEL is not configured")

        self._client = OpenAI(
            api_key=self._api_key,
            base_url=self._base_url,
            timeout=self._timeout,
        )
        return self._client


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value).strip())


def _coerce_positive_int(value: Any) -> int | None:
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def _build_default_sections(turn_count: int) -> list[ScriptSection]:
    remaining = max(0, int(turn_count))
    sections: list[ScriptSection] = []
    while remaining > 0:
        section_turn_count = min(_SECTION_TARGET_TURNS, remaining)
        if remaining > _SECTION_TARGET_TURNS and remaining - section_turn_count < 4:
            section_turn_count = max(1, remaining // 2)
        sections.append(
            ScriptSection(
                section_index=len(sections) + 1,
                title=f"Section {len(sections) + 1}",
                summary="Continue the dialogue naturally and move the scenario forward.",
                target_turn_count=section_turn_count,
            )
        )
        remaining -= section_turn_count
    return sections


def _strip_cue_brackets(value: str) -> str:
    match = _CUE_BRACKETS_PATTERN.match(value.strip())
    if not match:
        return value.strip()
    return re.sub(r"\s+", " ", (match.group(1) or "").strip())


def _is_chinese_language(value: str | None) -> bool:
    return (value or "").strip().lower().startswith("zh")


def _language_label(value: str | None) -> str:
    normalized = (value or "en").strip().lower()
    if normalized.startswith("zh"):
        return "Simplified Chinese"
    if normalized.startswith("en"):
        return "English"
    return value.strip() if value and value.strip() else "English"


def _cue_example(value: str | None) -> str:
    if _is_chinese_language(value):
        return "轻松自然地开口"
    return "Open in a relaxed, natural tone"


def _text_example(value: str | None) -> str:
    if _is_chinese_language(value):
        return "你好，现在方便聊一下吗？"
    return "Hi, do you have a minute?"
