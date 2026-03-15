from __future__ import annotations

import json
from datetime import datetime, timezone

from lsl.core.config import Settings
from lsl.modules.revision.llm_provider import LLMRevisionGenerator
from lsl.modules.revision.types import (
    RevisionGenerateRequest,
    RevisionPromptUtterance,
    RevisionSegment,
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
        task_id="task-1",
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
        "_plan_segments",
        lambda *, task_id, utterances, user_prompt: [
            RevisionSegment(segment_index=1, start_seq=1, end_seq=2, title="课堂反馈", summary="两句连续表达")
        ],
    )
    monkeypatch.setattr(
        generator,
        "_request_chat_completion",
        lambda *, task_id, request_name, messages: """
```json
{
  "items": [
    {
      "source_seqs": ["1"],
      "suggested_text": "i really enjoyed this class",
      "score": "91",
      "issue_tags": "不够自然，搭配问题",
      "explanations": ["改成更地道的口语表达", "保留原本积极语气"]
    },
    {
      "utterance_seq": 2,
      "suggested_text": "i went there last weekend",
      "score": 54,
      "issue_tags": ["语法错误", "不够自然", "语法错误"],
      "explanations": "修正时态/更符合日常口语"
    },
    {
      "utterance_seq": 99,
      "suggested_text": "should be ignored",
      "score": 80
    }
  ]
}
```""",
    )

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


def test_generate_includes_context_around_target_segment(monkeypatch) -> None:
    generator = LLMRevisionGenerator(_build_settings())
    req = RevisionGenerateRequest(
        task_id="task-2",
        user_prompt=None,
        utterances=[
            RevisionPromptUtterance(utterance_seq=0, speaker="student", text="hello"),
            RevisionPromptUtterance(utterance_seq=1, speaker="student", text="i like this"),
            RevisionPromptUtterance(utterance_seq=2, speaker="student", text="it is useful"),
            RevisionPromptUtterance(utterance_seq=3, speaker="teacher", text="that sounds good"),
        ],
    )
    captured_payloads: list[dict[str, object]] = []

    monkeypatch.setattr(
        generator,
        "_plan_segments",
        lambda *, task_id, utterances, user_prompt: [
            RevisionSegment(segment_index=1, start_seq=1, end_seq=2, title="学习反馈", summary="用户表达看法")
        ],
    )

    def fake_request_chat_completion(*, task_id, request_name, messages):
        if request_name.startswith("segment_revision"):
            user_message = next(item for item in messages if item["role"] == "user")
            content = user_message["content"]
            json_start = content.index("{")
            captured_payloads.append(json.loads(content[json_start:]))
            return """
{
  "items": [
    {"source_seqs": [1], "suggested_text": "I like this.", "score": 92},
    {"source_seqs": [2], "suggested_text": "It is useful.", "score": 95}
  ]
}
"""
        raise AssertionError(f"Unexpected request_name: {request_name}")

    monkeypatch.setattr(generator, "_request_chat_completion", fake_request_chat_completion)

    result = generator.generate(req)

    assert [item.source_seqs for item in result] == [[1], [2]]
    assert len(captured_payloads) == 1
    assert [item["utterance_seq"] for item in captured_payloads[0]["context_before"]] == [0]
    assert [item["utterance_seq"] for item in captured_payloads[0]["target_utterances"]] == [1, 2]
    assert [item["utterance_seq"] for item in captured_payloads[0]["context_after"]] == [3]


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
    messages = generator._build_segment_plan_messages(
        task_id="task-debug",
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
        task_id="task-debug",
        request_name="segment_plan",
        messages=messages,
        started_at=datetime(2026, 3, 8, 10, 0, tzinfo=timezone.utc),
        finished_at=datetime(2026, 3, 8, 10, 0, 1, tzinfo=timezone.utc),
        duration_ms=1000,
        response_content='{"segments":[]}',
        error_message=None,
        finish_reason="stop",
    )

    dump_text = debug_file.read_text(encoding="utf-8")
    assert "request_name: segment_plan" in dump_text
    assert "task_id: task-debug" in dump_text
    assert '"role": "system"' in dump_text
    assert '"role": "user"' in dump_text
    assert '{"segments":[]}' in dump_text
    assert "finish_reason: stop" in dump_text
