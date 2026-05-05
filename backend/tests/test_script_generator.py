from __future__ import annotations

from lsl.core.config import Settings
from lsl.modules.script.generator import FakeScriptGenerator, LlmScriptGenerator
from lsl.modules.script.types import ScriptGenerateRequest


def _build_request(*, language: str | None) -> ScriptGenerateRequest:
    return ScriptGenerateRequest(
        title="Practice",
        description=None,
        language=language,
        prompt="Practice a short conversation",
        turn_count=2,
        speaker_count=2,
    )


def test_llm_script_prompt_uses_target_language_for_cues() -> None:
    generator = LlmScriptGenerator(settings=Settings(SCRIPT_PROVIDER="llm"))

    english_messages = generator._build_stream_messages(
        req=_build_request(language="en-US"),
        speaker_names=["user-1", "user-2"],
    )
    english_system = english_messages[0]["content"]
    assert "cue must be concise English guidance" in english_system
    assert "Open in a relaxed, natural tone" in english_system

    chinese_messages = generator._build_stream_messages(
        req=_build_request(language="zh-CN"),
        speaker_names=["user-1", "user-2"],
    )
    chinese_system = chinese_messages[0]["content"]
    assert "cue must be concise Simplified Chinese guidance" in chinese_system
    assert "轻松自然地开口" in chinese_system


def test_fake_script_generator_uses_target_language_for_cues() -> None:
    generator = FakeScriptGenerator()

    english = generator.generate(_build_request(language="en-US"))
    assert english.utterances[0].cue == "Open in a relaxed, natural tone"
    assert english.utterances[0].text == "Hey, do you have a minute?"

    chinese = generator.generate(_build_request(language="zh-CN"))
    assert chinese.utterances[0].cue == "轻松自然地开口"
    assert chinese.utterances[0].text == "嘿，你现在方便吗？"
