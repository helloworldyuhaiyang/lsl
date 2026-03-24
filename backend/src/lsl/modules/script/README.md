# LSL - Script Module

Script 模块负责根据用户提示词生成带 cue 的对话脚本，并把结果落成：

- `f_type=2` 的文本 Session
- 一份 synthetic completed task / transcript
- 一份可直接进入 revise / tts 链路的 completed revision

## 当前接口

- `POST /scripts/generate-session` 生成 AI cue 脚本并创建 session

## 请求体

```json
{
  "title": "Team Feedback Practice",
  "description": "prepare for 1:1 feedback",
  "language": "en-US",
  "prompt": "我要练一个和同事讨论排期延期的对话，语气自然但不要太软。",
  "turn_count": 8,
  "speaker_count": 2,
  "difficulty": "intermediate",
  "cue_style": "自然口语、便于 TTS 演绎",
  "must_include": ["push back", "timeline"]
}
```

## 返回语义

接口成功后会直接返回：

- `session`：刚创建好的文本 Session
- `revision`：已完成的 revision，`suggested_text` 默认带 cue，可直接进入 revise 页面

## Cue 约束

- 每条生成 utterance 都必须有 cue
- cue 格式统一是 `[...]`
- revise 页面沿用现有橙色高亮输入体验
- TTS 继续从脚本里提取 cue，再剥离纯朗读文本

示例：

```text
[语气平稳但带一点坚持] I get the timeline pressure, but we may need two more days to do this properly.
```

## Provider 配置

```env
SCRIPT_PROVIDER=llm
SCRIPT_LLM_API_KEY=
SCRIPT_LLM_BASE_URL=
SCRIPT_LLM_MODEL=
SCRIPT_LLM_HTTP_TIMEOUT=60
```

说明：

- 默认可复用 revision 的 LLM 配置作为兜底。
- 本地联调可设 `SCRIPT_PROVIDER=fake`。
