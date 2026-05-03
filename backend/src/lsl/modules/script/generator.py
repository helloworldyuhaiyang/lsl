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
from lsl.modules.script.types import GeneratedScript, GeneratedScriptTurn, ScriptGenerateRequest, ScriptGenerator

logger = logging.getLogger(__name__)

_CUE_BRACKETS_PATTERN = re.compile(r"^\[?(.*?)\]?$")


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

    def _build_messages(self, *, req: ScriptGenerateRequest, speaker_names: list[str]) -> list[dict[str, str]]:
        system_prompt = (
            "You create cue-driven English speaking practice scripts.\n"
            "Return JSON only.\n"
            "Output schema:\n"
            "{\n"
            '  "utterances": [\n'
            '    {"speaker": "user-1", "cue": "轻松自然地开口", "text": "Hi, do you have a minute?"}\n'
            "  ]\n"
            "}\n"
            "Rules:\n"
            f"- Use only these speakers: {', '.join(speaker_names)}.\n"
            f"- Target about {req.turn_count} utterances.\n"
            "- Every utterance must include a non-empty cue and a non-empty spoken-English text.\n"
            "- cue must be concise Chinese guidance describing delivery, tone, emotion, rhythm, or subtext.\n"
            "- Do not include square brackets in the cue field.\n"
            "- text must be spoken English only and must not include cue markers.\n"
            "- Keep the dialogue natural, practical, and suitable for TTS playback.\n"
            "- Alternate speakers naturally.\n"
            "- 适当的增加 Hmm,Well..., Let me think… , uh... , so, basically, actually, but, however, while 等使其更加逼真。"
        )
        user_payload = {
            "title": req.title,
            "description": req.description,
            "language": req.language,
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
        system_prompt = (
            "You create cue-driven English speaking practice scripts.\n"
            "Return newline-delimited JSON only. Do not wrap the response in markdown.\n"
            "Each line must be one complete JSON object with this schema:\n"
            '{"speaker":"user-1","cue":"轻松自然地开口","text":"Hi, do you have a minute?"}\n'
            "Rules:\n"
            f"- Use only these speakers: {', '.join(speaker_names)}.\n"
            f"- Return exactly {req.turn_count} lines.\n"
            "- Every line must include a non-empty cue and a non-empty spoken-English text.\n"
            "- cue must be concise Chinese guidance describing delivery, tone, emotion, rhythm, or subtext.\n"
            "- Do not include square brackets in the cue field.\n"
            "- text must be spoken English only and must not include cue markers.\n"
            "- Keep the dialogue natural, practical, and suitable for TTS playback.\n"
            "- Alternate speakers naturally.\n"
            "- 适当的增加 Hmm,Well..., Let me think… , uh... , so, basically, actually, but, however, while 等使其更加逼真。"
        )
        user_payload = {
            "title": req.title,
            "description": req.description,
            "language": req.language,
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

    def _stream_generated_turns(
        self,
        *,
        req: ScriptGenerateRequest,
        speaker_names: list[str],
    ) -> Iterator[GeneratedScriptTurn]:
        started_at = time.monotonic()
        logger.info(
            "Script LLM stream request started model=%s turn_count=%s speaker_count=%s prompt_len=%s",
            self._model,
            req.turn_count,
            req.speaker_count,
            len(req.prompt),
        )
        stream = self._get_client().chat.completions.create(
            model=self._model,
            temperature=0.9,
            messages=self._build_stream_messages(req=req, speaker_names=speaker_names),
            stream=True,
            # 火山的扩展参数放这里，disabled 对应关闭深度思考
            extra_body={
                "thinking": {"type": "disabled"},
            },
        )
        logger.info(
            "Script LLM stream opened model=%s elapsed_ms=%s",
            self._model,
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
                    "Script LLM stream first chunk received model=%s elapsed_ms=%s",
                    self._model,
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
                    "Script LLM stream first content chunk received model=%s elapsed_ms=%s chars=%s",
                    self._model,
                    int((time.monotonic() - started_at) * 1000),
                    len(delta),
                )

            full_content_parts.append(delta)
            buffer += delta
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                line_count += 1
                turn = self._parse_stream_line(line=line, speaker_names=speaker_names, index=yielded_count)
                if turn is None:
                    continue
                if not first_turn_logged:
                    first_turn_logged = True
                    logger.info(
                        "Script LLM stream first valid turn parsed model=%s elapsed_ms=%s chunks=%s lines=%s buffered_chars=%s",
                        self._model,
                        int((time.monotonic() - started_at) * 1000),
                        non_empty_chunk_count,
                        line_count,
                        len(buffer),
                    )
                yield turn
                yielded_count += 1
                if yielded_count >= req.turn_count:
                    logger.info(
                        "Script LLM stream stopped after target turns model=%s turns=%s chunks=%s lines=%s elapsed_ms=%s",
                        self._model,
                        yielded_count,
                        non_empty_chunk_count,
                        line_count,
                        int((time.monotonic() - started_at) * 1000),
                    )
                    return

        turn = self._parse_stream_line(line=buffer, speaker_names=speaker_names, index=yielded_count)
        if turn is not None and yielded_count < req.turn_count:
            if not first_turn_logged:
                logger.info(
                    "Script LLM stream first valid turn parsed at stream end model=%s elapsed_ms=%s chunks=%s lines=%s buffered_chars=%s",
                    self._model,
                    int((time.monotonic() - started_at) * 1000),
                    non_empty_chunk_count,
                    line_count,
                    len(buffer),
                )
            yield turn
            yielded_count += 1

        if yielded_count > 0:
            logger.info(
                "Script LLM stream finished with parsed turns model=%s turns=%s chunks=%s raw_chunks=%s lines=%s total_chars=%s elapsed_ms=%s",
                self._model,
                yielded_count,
                non_empty_chunk_count,
                chunk_count,
                line_count,
                sum(len(part) for part in full_content_parts),
                int((time.monotonic() - started_at) * 1000),
            )
            return

        logger.warning(
            "Script LLM stream ended without valid NDJSON turns; attempting full response parse model=%s chunks=%s raw_chunks=%s lines=%s total_chars=%s elapsed_ms=%s",
            self._model,
            non_empty_chunk_count,
            chunk_count,
            line_count,
            sum(len(part) for part in full_content_parts),
            int((time.monotonic() - started_at) * 1000),
        )
        parsed = self._parse_response_content(content="".join(full_content_parts))
        for turn in self._normalize_generated_script(raw=parsed, speaker_names=speaker_names, req=req).utterances:
            yield turn
            yielded_count += 1
        logger.info(
            "Script LLM stream full response parse yielded turns model=%s turns=%s elapsed_ms=%s",
            self._model,
            yielded_count,
            int((time.monotonic() - started_at) * 1000),
        )

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


def _strip_cue_brackets(value: str) -> str:
    match = _CUE_BRACKETS_PATTERN.match(value.strip())
    if not match:
        return value.strip()
    return re.sub(r"\s+", " ", (match.group(1) or "").strip())
