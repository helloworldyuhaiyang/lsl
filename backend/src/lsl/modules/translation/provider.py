from __future__ import annotations

import json
import re
from typing import Any, Iterator

from json_repair import repair_json
from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam
from openai.types.chat.chat_completion_system_message_param import ChatCompletionSystemMessageParam
from openai.types.chat.chat_completion_user_message_param import ChatCompletionUserMessageParam

from lsl.core.config import Settings
from lsl.modules.translation.types import TranslationGenerateRequest, TranslationGenerator, TranslationSuggestion

_CODE_FENCE_JSON_RE = re.compile(r"```(?:json)?\s*(.+?)\s*```", re.DOTALL | re.IGNORECASE)

_TRANSLATION_SYSTEM_PROMPT = """You are a translation assistant for English listening practice.

Return a JSON object only.
Translate each target item into natural Simplified Chinese.
Preserve the speaker's meaning, tone, and context.
Do not translate delivery CUEs in square brackets as spoken content; use them only to understand tone.
Keep translations concise and useful for learners.

Output schema:
{
  "items": [
    {
      "source_item_key": "item id",
      "translated_text": "中文译文"
    }
  ]
}
"""


def create_translation_generator(settings: Settings) -> TranslationGenerator:
    provider = (settings.TRANSLATION_PROVIDER or "fake").strip().lower()
    if provider == "llm":
        return LLMTranslationGenerator(settings)
    if provider == "fake":
        return FakeTranslationGenerator()
    raise ValueError(f"Unsupported TRANSLATION_PROVIDER: {provider}")


class FakeTranslationGenerator:
    provider_name = "fake"

    def generate(self, req: TranslationGenerateRequest) -> list[TranslationSuggestion]:
        return [
            TranslationSuggestion(
                source_item_key=item.source_item_key,
                translated_text=f"译文：{item.source_text}",
            )
            for item in req.items
        ]

    def generate_progressively(self, req: TranslationGenerateRequest) -> Iterator[list[TranslationSuggestion]]:
        if not req.items:
            return
        yield self.generate(req)


class LLMTranslationGenerator:
    provider_name = "llm"

    def __init__(self, settings: Settings) -> None:
        self._api_key = settings.TRANSLATION_LLM_API_KEY
        self._base_url = settings.TRANSLATION_LLM_BASE_URL
        self._model = settings.TRANSLATION_LLM_MODEL
        self._timeout = float(settings.TRANSLATION_LLM_HTTP_TIMEOUT)
        self._client: OpenAI | None = None

    def generate(self, req: TranslationGenerateRequest) -> list[TranslationSuggestion]:
        suggestions: list[TranslationSuggestion] = []
        for batch in self.generate_progressively(req):
            suggestions.extend(batch)
        return suggestions

    def generate_progressively(self, req: TranslationGenerateRequest) -> Iterator[list[TranslationSuggestion]]:
        if not req.items:
            return
        content = self._request_chat_completion(messages=self._build_messages(req))
        yield self._parse_response(content)

    def _request_chat_completion(self, *, messages: list[ChatCompletionMessageParam]) -> str:
        response = self._get_client().chat.completions.create(
            model=self._model,
            temperature=0.1,
            messages=messages,
            timeout=self._timeout,
            reasoning_effort="minimal",
            extra_body={
                "thinking": {"type": "disabled"},
            },
        )
        if not response.choices:
            raise RuntimeError("LLM returned no choices")
        choice = response.choices[0]
        content = choice.message.content
        if content is None or not content.strip():
            raise RuntimeError("LLM returned empty content")
        finish_reason = getattr(choice, "finish_reason", None)
        if finish_reason not in (None, "stop"):
            raise RuntimeError(f"LLM stopped with finish_reason={finish_reason}")
        return content

    @staticmethod
    def _build_messages(req: TranslationGenerateRequest) -> list[ChatCompletionMessageParam]:
        payload = {
            "source_type": req.source_type,
            "source_entity_id": req.source_entity_id,
            "source_language": req.source_language,
            "target_language": req.target_language,
            "items": [
                {
                    "source_item_key": item.source_item_key,
                    "source_seq": item.source_seq,
                    "speaker": item.speaker,
                    "text": item.source_text,
                }
                for item in req.items
            ],
        }
        system_message: ChatCompletionSystemMessageParam = {
            "role": "system",
            "content": _TRANSLATION_SYSTEM_PROMPT,
        }
        user_message: ChatCompletionUserMessageParam = {
            "role": "user",
            "content": "Translate these listening-practice items.\nInput JSON:\n"
            f"{json.dumps(payload, ensure_ascii=False, indent=2)}",
        }
        return [system_message, user_message]

    @staticmethod
    def _parse_response(content: str) -> list[TranslationSuggestion]:
        parsed = LLMTranslationGenerator._loads_json(content)
        raw_items = parsed.get("items") if isinstance(parsed, dict) else None
        if not isinstance(raw_items, list):
            raise RuntimeError("LLM returned no translation items")
        suggestions: list[TranslationSuggestion] = []
        for raw_item in raw_items:
            if not isinstance(raw_item, dict):
                continue
            source_item_key = str(raw_item.get("source_item_key") or "").strip()
            translated_text = str(raw_item.get("translated_text") or "").strip()
            if source_item_key and translated_text:
                suggestions.append(
                    TranslationSuggestion(
                        source_item_key=source_item_key,
                        translated_text=translated_text,
                    )
                )
        if not suggestions:
            raise RuntimeError("LLM returned no valid translation items")
        return suggestions

    @staticmethod
    def _loads_json(content: str) -> Any:
        text = content.strip()
        match = _CODE_FENCE_JSON_RE.search(text)
        if match:
            text = match.group(1).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return json.loads(repair_json(text))

    def _get_client(self) -> OpenAI:
        if self._client is None:
            if not self._api_key:
                raise RuntimeError("TRANSLATION_LLM_API_KEY is required")
            self._client = OpenAI(api_key=self._api_key, base_url=self._base_url)
        return self._client
