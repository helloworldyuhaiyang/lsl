from __future__ import annotations

import json
from datetime import datetime, timezone

from lsl.core.config import Settings
from lsl.modules.revision.llm_provider import LLMRevisionGenerator
from lsl.modules.revision.types import (
    RevisionGenerateRequest,
    RevisionPromptUtterance,
    RevisionSection,
)


def _build_settings() -> Settings:
    return Settings(
        REVISION_PROVIDER="llm",
        REVISION_LLM_API_KEY="test-key",
        REVISION_LLM_BASE_URL="https://example.com/v1",
        REVISION_LLM_MODEL="test-model",
    )


def test_generate_normalizes_llm_response(monkeypatch) -> None:
    generator = LLMRevisionGenerator(_build_settings())
    req = RevisionGenerateRequest(
        transcript_id="task-1",
        user_prompt="请改得更自然一点",
        utterances=[
            RevisionPromptUtterance(
                utterance_seq=1,
                speaker="student",
                text="i really like this class",
            ),
            RevisionPromptUtterance(
                utterance_seq=2,
                speaker="student",
                text="i go there last weekend",
            ),
        ],
    )

    monkeypatch.setattr(
        generator,
        "_plan_sections",
        lambda *, transcript_id, utterances, user_prompt: [
            RevisionSection(section_index=1, start_seq=1, end_seq=2, title="课堂反馈", summary="两句连续表达")
        ],
    )
    def fake_stream(*, transcript_id, request_name, messages):
        yield "\n".join(
            [
                json.dumps(
                    {
                        "source_seqs": ["1"],
                        "suggested_text": "i really enjoyed this class",
                        "score": "91",
                        "issue_tags": "不够自然，搭配问题",
                        "explanations": ["改成更地道的口语表达", "保留原本积极语气"],
                    }
                ),
                json.dumps(
                    {
                        "utterance_seq": 2,
                        "suggested_text": "i went there last weekend",
                        "score": 54,
                        "issue_tags": ["语法错误", "不够自然", "语法错误"],
                        "explanations": "修正时态/更符合日常口语",
                    }
                ),
                json.dumps(
                    {
                        "utterance_seq": 99,
                        "suggested_text": "should be ignored",
                        "score": 80,
                    }
                ),
                "",
            ]
        )

    monkeypatch.setattr(generator, "_request_chat_completion_stream", fake_stream)

    result = generator.generate(req)

    assert [item.source_seqs for item in result] == [[1], [2]]

    first = result[0]
    assert first.suggested_text == "i really enjoyed this class"
    assert first.score == 91
    assert first.issue_tags == "不够自然, 搭配问题"
    assert first.explanations == "改成更地道的口语表达 保留原本积极语气"

    second = result[1]
    assert second.suggested_text == "i went there last weekend"
    assert second.score == 54
    assert second.issue_tags == "语法错误, 不够自然"
    assert second.explanations == "修正时态/更符合日常口语"


def test_get_client_ignores_proxy_env(monkeypatch) -> None:
    monkeypatch.setenv("ALL_PROXY", "socks5://127.0.0.1:9999")
    monkeypatch.setenv("HTTPS_PROXY", "socks5://127.0.0.1:9999")

    generator = LLMRevisionGenerator(_build_settings())

    client = generator._get_client()

    assert client is generator._get_client()


def test_short_transcript_skips_section_plan(monkeypatch) -> None:
    generator = LLMRevisionGenerator(_build_settings())
    req = RevisionGenerateRequest(
        transcript_id="task-short",
        user_prompt=None,
        utterances=[
            RevisionPromptUtterance(utterance_seq=0, speaker="student", text="hello"),
            RevisionPromptUtterance(utterance_seq=1, speaker="student", text="thanks"),
        ],
    )

    def fail_plan_sections(*, transcript_id, utterances, user_prompt):
        raise AssertionError("section_plan should be skipped for short transcripts")

    def fake_stream(*, transcript_id, request_name, messages):
        yield (
            '{"source_seqs":[0],"suggested_text":"Hello.","score":95}\n'
            '{"source_seqs":[1],"suggested_text":"Thanks.","score":95}\n'
        )

    monkeypatch.setattr(generator, "_plan_sections", fail_plan_sections)
    monkeypatch.setattr(generator, "_request_chat_completion_stream", fake_stream)

    result = generator.generate(req)

    assert [item.source_seqs for item in result] == [[0], [1]]


def test_generate_includes_context_around_target_section(monkeypatch) -> None:
    generator = LLMRevisionGenerator(_build_settings())
    req = RevisionGenerateRequest(
        transcript_id="task-2",
        user_prompt=None,
        utterances=[
            RevisionPromptUtterance(utterance_seq=0, speaker="student", text="hello"),
            RevisionPromptUtterance(utterance_seq=1, speaker="student", text="i like this"),
            RevisionPromptUtterance(utterance_seq=2, speaker="student", text="it is useful"),
            RevisionPromptUtterance(utterance_seq=3, speaker="teacher", text="that sounds good"),
        ],
    )
    captured_payloads: list[dict[str, object]] = []

    def fake_stream(*, transcript_id, request_name, messages):
        if request_name.startswith("section_revision"):
            user_message = next(item for item in messages if item["role"] == "user")
            content = user_message["content"]
            json_start = content.index("{")
            captured_payloads.append(json.loads(content[json_start:]))
            yield (
                '{"source_seqs":[1],"suggested_text":"I like this.","score":92}\n'
                '{"source_seqs":[2],"suggested_text":"It is useful.","score":95}\n'
            )
            return
        raise AssertionError(f"Unexpected request_name: {request_name}")

    monkeypatch.setattr(generator, "_request_chat_completion_stream", fake_stream)

    result = generator._generate_single_section_revision(
        transcript_id=req.transcript_id,
        utterances=req.utterances,
        user_prompt=req.user_prompt,
        target_language=req.target_language,
        cue_language=req.cue_language,
        section=RevisionSection(section_index=1, start_seq=1, end_seq=2, title="学习反馈", summary="用户表达看法"),
        utterance_index_by_seq={int(item.utterance_seq): index for index, item in enumerate(req.utterances)},
    )

    assert [item.source_seqs for item in result] == [[1], [2]]
    assert len(captured_payloads) == 1
    assert [item["utterance_seq"] for item in captured_payloads[0]["context_before"]] == [0]
    assert [item["utterance_seq"] for item in captured_payloads[0]["target_utterances"]] == [1, 2]
    assert [item["utterance_seq"] for item in captured_payloads[0]["context_after"]] == [3]


def test_revision_prompt_includes_existing_cue_additions(monkeypatch) -> None:
    generator = LLMRevisionGenerator(_build_settings())
    req = RevisionGenerateRequest(
        transcript_id="task-cue",
        user_prompt=None,
        target_language="en-US",
        utterances=[
            RevisionPromptUtterance(
                utterance_seq=0,
                speaker="student",
                text="hello",
                addions={"cue": "轻松自然地开口"},
            ),
        ],
    )
    captured_payloads: list[dict[str, object]] = []

    monkeypatch.setattr(
        generator,
        "_plan_sections",
        lambda *, transcript_id, utterances, user_prompt: [
            RevisionSection(section_index=1, start_seq=0, end_seq=0, title="Greeting", summary="One greeting")
        ],
    )

    def fake_stream(*, transcript_id, request_name, messages):
        if request_name.startswith("section_revision"):
            user_message = next(item for item in messages if item["role"] == "user")
            content = user_message["content"]
            captured_payloads.append(json.loads(content[content.index("{"):]))
            yield '{"source_seqs":[0],"suggested_text":"[Open naturally] Hello.","score":95}\n'
            return
        raise AssertionError(f"Unexpected request_name: {request_name}")

    monkeypatch.setattr(generator, "_request_chat_completion_stream", fake_stream)

    result = generator.generate(req)

    assert result[0].suggested_text == "[Open naturally] Hello."
    target_utterance = captured_payloads[0]["target_utterances"][0]
    assert target_utterance["addions"] == {"cue": "轻松自然地开口"}


def test_revision_prompt_uses_target_language_for_cues() -> None:
    generator = LLMRevisionGenerator(_build_settings())

    english_messages = generator._build_section_revision_messages(
        transcript_id="task-en",
        section=RevisionSection(section_index=1, start_seq=0, end_seq=0),
        user_prompt=None,
        target_language="en-US",
        cue_language=None,
        context_before=[],
        target_utterances=[
            RevisionPromptUtterance(utterance_seq=0, speaker="student", text="hello")
        ],
        context_after=[],
    )
    english_system = next(item for item in english_messages if item["role"] == "system")["content"]
    assert "Include one short English delivery cue in every rewritten script" in english_system
    assert "suggested_text must be a single editable script string that starts with exactly one delivery CUE" in english_system
    assert "translate or rewrite that CUE into English" in english_system
    assert "[Open with relaxed, natural curiosity]" in english_system

    chinese_messages = generator._build_section_revision_messages(
        transcript_id="task-zh",
        section=RevisionSection(section_index=1, start_seq=0, end_seq=0),
        user_prompt=None,
        target_language="zh-CN",
        cue_language=None,
        context_before=[],
        target_utterances=[
            RevisionPromptUtterance(utterance_seq=0, speaker="student", text="你好")
        ],
        context_after=[],
    )
    chinese_system = next(item for item in chinese_messages if item["role"] == "system")["content"]
    assert "Include one short Simplified Chinese delivery cue in every rewritten script" in chinese_system
    assert "translate or rewrite that CUE into Simplified Chinese" in chinese_system
    assert "[用轻松自然的语气开口]" in chinese_system

    mixed_messages = generator._build_section_revision_messages(
        transcript_id="task-en-cue-zh",
        section=RevisionSection(section_index=1, start_seq=0, end_seq=0),
        user_prompt=None,
        target_language="en-US",
        cue_language="zh-CN",
        context_before=[],
        target_utterances=[
            RevisionPromptUtterance(utterance_seq=0, speaker="student", text="hello")
        ],
        context_after=[],
    )
    mixed_system = next(item for item in mixed_messages if item["role"] == "system")["content"]
    assert "fluent, natural spoken English" in mixed_system
    assert "Include one short Simplified Chinese delivery cue in every rewritten script" in mixed_system
    assert "translate or rewrite that CUE into Simplified Chinese" in mixed_system
    assert "[用轻松自然的语气开口] What did you do last weekend?" in mixed_system


def test_append_debug_dump_writes_request_and_response(tmp_path) -> None:
    debug_file = tmp_path / "llm_revision.txt"
    generator = LLMRevisionGenerator(
        Settings(
            REVISION_PROVIDER="llm",
            REVISION_LLM_API_KEY="test-key",
            REVISION_LLM_BASE_URL="https://example.com/v1",
            REVISION_LLM_MODEL="test-model",
            REVISION_LLM_DEBUG_FILE=str(debug_file),
        )
    )
    messages = generator._build_section_plan_messages(
        transcript_id="task-debug",
        utterances=[
            RevisionPromptUtterance(
                utterance_seq=0,
                speaker="student",
                text="i like this",
            )
        ],
        user_prompt="请帮我改自然一点",
    )

    generator._append_debug_dump(
        transcript_id="task-debug",
        request_name="section_plan",
        messages=messages,
        started_at=datetime(2026, 3, 8, 10, 0, tzinfo=timezone.utc),
        finished_at=datetime(2026, 3, 8, 10, 0, 1, tzinfo=timezone.utc),
        duration_ms=1000,
        response_content='{"sections":[]}',
        error_message=None,
        finish_reason="stop",
    )

    dump_text = debug_file.read_text(encoding="utf-8")
    assert "request_name: section_plan" in dump_text
    assert "transcript_id: task-debug" in dump_text
    assert '"role": "system"' in dump_text
    assert '"role": "user"' in dump_text
    assert '{"sections":[]}' in dump_text
    assert "finish_reason: stop" in dump_text
