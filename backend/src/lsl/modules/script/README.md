# LSL - Script Module

Script 模块负责根据用户提示词生成带 cue 的对话脚本，并把结果落成：

- `f_type=2` 的文本 Session
- 一条 `ai_script_generation` job
- 一份 AI script 来源的 completed transcript
- 一份可直接进入 revise / tts 链路的 completed revision

## 当前接口

- `POST /scripts/generate-session` 创建文本 session、generation 记录和异步 job
- `GET /scripts/generations/{generation_id}` 查询 generation 状态
- `GET /scripts/generations/{generation_id}/preview` 查询生成中的逐条脚本预览

## 请求体

```json
{
  "title": "Team Feedback Practice",
  "description": "prepare for 1:1 feedback",
  "target_language": "en-US",
  "cue_language": "zh-CN",
  "prompt": "我要练一个和同事讨论排期延期的对话，语气自然但不要太软。",
  "turn_count": 8,
  "speaker_count": 2,
  "difficulty": "intermediate",
  "cue_style": "自然口语、便于 TTS 演绎",
  "must_include": ["push back", "timeline"]
}
```

## 返回语义

接口成功后立即返回：

- `session`：刚创建好的文本 Session
- `generation`：脚本生成记录
- `job`：`job_type=ai_script_generation` 的异步 job

job 完成后会写入：

- `transcript`：`source_type=ai_script`，`source_entity_id=generation_id`
- `revision`：已完成的 revision，`suggested_text` 默认带 cue，可直接进入 revise 页面

语言语义：

- `target_language` 控制正文目标语言，并写入 session / generation / transcript。
- `cue_language` 控制生成 CUE 的语言，只影响 `[...]` 内的提示。
- 如果未传 `cue_language`，默认跟随 `target_language`。

job 运行中会持续更新 `preview_items_json`。前端 Revise 等待态可以先展示 preview items，等 job 完成后再切换到正式 revision。

当 `turn_count > 16` 时，job 会先生成章节规划并写入 `plan_sections_json`，再按章节顺序生成脚本内容。AI script 章节生成不并发执行，避免上下文断裂、重复铺垫或话题跳跃。

preview 接口在生成中可返回：

- `generation.raw_result.stage="planning"`：正在生成章节规划
- `generation.plan_sections`：规划好的章节、摘要和目标轮数
- `items`：已经生成出的逐轮脚本 preview

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
