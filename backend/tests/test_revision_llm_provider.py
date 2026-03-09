from __future__ import annotations

from datetime import datetime, timezone

from lsl.core.config import Settings
from lsl.modules.revision.llm_provider import LLMRevisionGenerator
from lsl.modules.revision.types import RevisionGenerateRequest, RevisionPromptUtterance


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
                start_time=0,
                end_time=1200,
            ),
            RevisionPromptUtterance(
                utterance_seq=2,
                speaker="student",
                text="i go there last weekend",
                start_time=1200,
                end_time=2400,
            ),
        ],
    )

    monkeypatch.setattr(
        generator,
        "_request_revision",
        lambda *, task_id, utterances, user_prompt: """
```json
{
  "items": [
    {
      "utterance_seq": "1",
      "suggested_text": "i really enjoyed this class",
      "suggested_cue": "自然的 / 轻松的 / 课堂讨论",
      "score": "91",
      "issue_tags": "不够自然，搭配问题",
      "explanations": ["改成更地道的口语表达", "保留原本积极语气"]
    },
    {
      "utterance_seq": 2,
      "suggested_text": "i went there last weekend",
      "suggested_cue": "",
      "score": null,
      "issue_tags": ["语法错误", "不够自然", "语法错误"],
      "explanations": "修正时态/更符合日常口语"
    },
    {
      "utterance_seq": 99,
      "suggested_text": "should be ignored"
    }
  ]
}
```""",
    )

    result = generator.generate(req)

    assert [item.utterance_seq for item in result] == [1, 2]

    first = result[0]
    assert first.suggested_text == "I really enjoyed this class."
    assert first.suggested_cue == "自然的 / 轻松的 / 课堂讨论"
    assert first.score == 91
    assert first.issue_tags == "不够自然, 搭配问题"
    assert first.explanations == "改成更地道的口语表达 保留原本积极语气"

    second = result[1]
    assert second.suggested_text == "I went there last weekend."
    assert second.suggested_cue is None
    assert second.score == 54
    assert second.issue_tags == "语法错误, 不够自然"
    assert second.explanations == "修正时态/更符合日常口语"


def test_get_client_ignores_proxy_env(monkeypatch) -> None:
    monkeypatch.setenv("ALL_PROXY", "socks5://127.0.0.1:9999")
    monkeypatch.setenv("HTTPS_PROXY", "socks5://127.0.0.1:9999")

    generator = LLMRevisionGenerator(_build_settings())

    client = generator._get_client()

    assert client is generator._get_client()


def test_generate_prefers_full_transcript_context(monkeypatch) -> None:
    generator = LLMRevisionGenerator(_build_settings())
    req = RevisionGenerateRequest(
        task_id="task-2",
        user_prompt=None,
        utterances=[
            RevisionPromptUtterance(
                utterance_seq=0,
                speaker="student",
                text="i like this",
                start_time=0,
                end_time=1000,
            ),
            RevisionPromptUtterance(
                utterance_seq=1,
                speaker="teacher",
                text="that sounds good",
                start_time=1000,
                end_time=2000,
            ),
        ],
    )
    utterance_counts: list[int] = []

    def fake_request_revision(*, task_id, utterances, user_prompt):
        utterance_counts.append(len(utterances))
        return """
{
  "items": [
    {"utterance_seq": 0, "suggested_text": "I like this.", "score": 92},
    {"utterance_seq": 1, "suggested_text": "That sounds good.", "score": 95}
  ]
}
"""

    monkeypatch.setattr(generator, "_request_revision", fake_request_revision)

    result = generator.generate(req)

    assert utterance_counts == [2]
    assert [item.utterance_seq for item in result] == [0, 1]


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
    utterances = [
        RevisionPromptUtterance(
            utterance_seq=0,
            speaker="student",
            text="i like this",
            start_time=0,
            end_time=1000,
        )
    ]
    messages = generator._build_messages(
        task_id="task-debug",
        utterances=utterances,
        user_prompt="请帮我改自然一点",
    )

    generator._append_debug_dump(
        task_id="task-debug",
        messages=messages,
        started_at=datetime(2026, 3, 8, 10, 0, tzinfo=timezone.utc),
        finished_at=datetime(2026, 3, 8, 10, 0, 1, tzinfo=timezone.utc),
        duration_ms=1000,
        response_content='{"items":[]}',
        error_message=None,
    )

    dump_text = debug_file.read_text(encoding="utf-8")
    assert "task_id: task-debug" in dump_text
    assert '"role": "system"' in dump_text
    assert '"role": "user"' in dump_text
    assert '{"items":[]}' in dump_text
