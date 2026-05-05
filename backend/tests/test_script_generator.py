from __future__ import annotations

from lsl.core.config import Settings
from lsl.modules.script.generator import FakeScriptGenerator, LlmScriptGenerator
from lsl.modules.script.types import ScriptGenerateRequest


def _build_request(*, target_language: str | None, cue_language: str | None = None) -> ScriptGenerateRequest:
    return ScriptGenerateRequest(
        title="Practice",
        description=None,
        target_language=target_language,
        cue_language=cue_language,
        prompt="Practice a short conversation",
        turn_count=2,
        speaker_count=2,
    )


def test_llm_script_prompt_uses_target_language_for_cues() -> None:
    generator = LlmScriptGenerator(settings=Settings(SCRIPT_PROVIDER="llm"))

    english_messages = generator._build_stream_messages(
        req=_build_request(target_language="en-US"),
        speaker_names=["user-1", "user-2"],
    )
    english_system = english_messages[0]["content"]
    assert "cue must be concise English guidance" in english_system
    assert "Open in a relaxed, natural tone" in english_system

    chinese_messages = generator._build_stream_messages(
        req=_build_request(target_language="zh-CN"),
        speaker_names=["user-1", "user-2"],
    )
    chinese_system = chinese_messages[0]["content"]
    assert "cue must be concise Simplified Chinese guidance" in chinese_system
    assert "轻松自然地开口" in chinese_system

    mixed_messages = generator._build_stream_messages(
        req=_build_request(target_language="en-US", cue_language="zh-CN"),
        speaker_names=["user-1", "user-2"],
    )
    mixed_system = mixed_messages[0]["content"]
    assert "non-empty spoken English text" in mixed_system
    assert "cue must be concise Simplified Chinese guidance" in mixed_system
    assert '"cue":"轻松自然地开口"' in mixed_system
    assert '"text":"Hi, do you have a minute?"' in mixed_system


def test_fake_script_generator_uses_target_language_for_cues() -> None:
    generator = FakeScriptGenerator()

    english = generator.generate(_build_request(target_language="en-US"))
    assert english.utterances[0].cue == "Open in a relaxed, natural tone"
    assert english.utterances[0].text == "Hey, do you have a minute?"

    chinese = generator.generate(_build_request(target_language="zh-CN"))
    assert chinese.utterances[0].cue == "轻松自然地开口"
    assert chinese.utterances[0].text == "嘿，你现在方便吗？"

    mixed = generator.generate(_build_request(target_language="en-US", cue_language="zh-CN"))
    assert mixed.utterances[0].cue == "轻松自然地开口"
    assert mixed.utterances[0].text == "Hey, do you have a minute?"
