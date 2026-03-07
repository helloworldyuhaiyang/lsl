from __future__ import annotations

import json
import re
from typing import Any
from openai import OpenAI

from lsl.core.config import Settings
from lsl.modules.revision.types import (
    FakeRevisionGenerator,
    RevisionGenerateRequest,
    RevisionGenerator,
    RevisionSuggestion,
)


class LLMRevisionGenerator:
    provider_name = "llm"

    def __init__(self, settings: Settings) -> None:
        self._api_key = settings.REVISION_LLM_API_KEY
        self._base_url = settings.REVISION_LLM_BASE_URL
        self._model = settings.REVISION_LLM_MODEL
        self._timeout = settings.REVISION_LLM_HTTP_TIMEOUT

    def generate(self, req: RevisionGenerateRequest) -> list[RevisionSuggestion]:
        if not self._api_key:
            raise RuntimeError("REVISION_LLM_API_KEY is missing")

        client = OpenAI(
            base_url=self._base_url,
            api_key=self._api_key,
            timeout=self._timeout,
        )
        completion = client.chat.completions.create(
            model=self._model,
            messages=self._build_messages(req),
            temperature=0.3,
        )
        content = completion.choices[0].message.content or ""
        payload = self._parse_json_payload(content)
        return self._parse_suggestions(payload)

    @staticmethod
    def _build_messages(req: RevisionGenerateRequest) -> list[dict[str, str]]:
        prompt_payload = {
            "task_id": req.task_id,
            "user_prompt": req.user_prompt,
            "utterances": [
                {
                    "utterance_seq": item.utterance_seq,
                    "speaker": item.speaker,
                    "text": item.text,
                    "start_time": item.start_time,
                    "end_time": item.end_time,
                }
                for item in req.utterances
            ],
        }
        return [
            {
                "role": "system",
                "content": (
                    "你是一名英文口语脚本 revise 助手。"
                    "你会读取 ASR utterances，并返回严格 JSON。"
                    "请逐句输出更自然、正确、可学习的英文表达。"
                    "每条都必须返回 utterance_seq, suggested_text, suggested_cue, score, issue_tags, explanations。"
                    "score 必须是 0 到 100 的整数。"
                    "suggested_cue 采用 [场景/ 情绪 / 语气 ] 格式。"
                    "只返回 JSON，不要输出 markdown、代码块说明或额外文字。"
                ),
            },
            {
                "role": "user",
                "content": json.dumps(prompt_payload, ensure_ascii=False),
            },
        ]

    @staticmethod
    def _parse_json_payload(content: str) -> dict[str, Any]:
        stripped = content.strip()
        if stripped.startswith("```"):
            stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
            stripped = re.sub(r"\s*```$", "", stripped)

        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Failed to parse Ark revision response: {exc}") from exc

        if not isinstance(payload, dict):
            raise RuntimeError("Ark revision response must be a JSON object")
        return payload

    @staticmethod
    def _parse_suggestions(payload: dict[str, Any]) -> list[RevisionSuggestion]:
        raw_items = payload.get("items")
        if not isinstance(raw_items, list):
            raise RuntimeError("Ark revision response must include items[]")

        suggestions: list[RevisionSuggestion] = []
        for raw in raw_items:
            if not isinstance(raw, dict):
                continue

            utterance_seq = raw.get("utterance_seq")
            suggested_text = raw.get("suggested_text")
            if not isinstance(utterance_seq, int) or not isinstance(suggested_text, str) or not suggested_text.strip():
                continue

            suggested_cue = raw.get("suggested_cue")
            score = raw.get("score")
            issue_tags = raw.get("issue_tags")
            explanations = raw.get("explanations")

            suggestions.append(
                RevisionSuggestion(
                    utterance_seq=utterance_seq,
                    suggested_text=suggested_text.strip(),
                    suggested_cue=suggested_cue.strip() if isinstance(suggested_cue, str) and suggested_cue.strip() else None,
                    score=max(0, min(int(score), 100)) if isinstance(score, int) else 80,
                    issue_tags=[item.strip() for item in issue_tags if isinstance(item, str) and item.strip()]
                    if isinstance(issue_tags, list)
                    else [],
                    explanations=[item.strip() for item in explanations if isinstance(item, str) and item.strip()]
                    if isinstance(explanations, list)
                    else [],
                )
            )

        return suggestions


def create_revision_generator(settings: Settings) -> RevisionGenerator:
    provider = (settings.REVISION_PROVIDER or "fake").strip().lower()
    if provider == "ark":
        return LLMRevisionGenerator(settings)
    if provider == "fake":
        return FakeRevisionGenerator()
    raise ValueError(f"Unsupported REVISION_PROVIDER: {provider}")
