# LSL - Revision Module

Revision 模块负责 transcript revise 的生成、持久化和用户编辑态保存。当前实现已经从“单句 item”升级为“span item”：一张 revise 卡片可以覆盖一个或多个相邻 utterance。

设计原则：
- 接口归 `revision` 模块所有，不挂在 `session` 模块下。
- RevisionService 通过 `SessionService` 和 `TaskService` 获取 `session/task/transcript`，不跨模块直接访问别人的 repo。
- 当前阶段每个 `session` 只保留一份当前 revise 结果，不保存历史版本。
- `POST /revisions` 是异步生成接口：先返回 `generating`，后台继续跑 LLM。
- revise item 以 `source_seqs` 表达原始 utterance span，不再强制一条原句对应一条 revise 卡片。

## 当前接口设计

- `POST /revisions` 创建或覆盖当前 session 的 revise 任务，立即返回当前 revision
- `GET /revisions?session_id={session_id}` 查询当前 session 的 revise 结果
- `PATCH /revisions/items/{item_id}` 保存单条 revise span 的用户编辑结果

## 环境变量

```env
REVISION_PROVIDER=fake
REVISION_LLM_API_KEY=your-real-ark-api-key
REVISION_LLM_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
REVISION_LLM_MODEL=doubao-seed-2-0-pro-260215
REVISION_LLM_HTTP_TIMEOUT=120
REVISION_LLM_DEBUG_FILE=./revision_debug.log
```

说明：
- `REVISION_PROVIDER=fake` 时，返回固定调试 revise 文案，便于前后端联调。
- `REVISION_PROVIDER=llm` 时，调用大模型执行“先总结分段，再按段并发 revise”。
- 当前实现不再回退本地规则生成 `suggested_text / score / suggested_cue`，这些字段必须由 LLM 返回。
- LLM 返回的 JSON 会先走 `json.loads`，失败后再走 `json-repair`。

## 接口语义

### 1) `POST /revisions`

请求体：

```json
{
  "session_id": "8f85f0be-6f53-4ca4-b6fe-b5d3f0a64047",
  "user_prompt": "请改成更自然、适合迪拜和印度口语对话风格",
  "force": true
}
```

行为约束：
- `session_id` 必填。
- `user_prompt` 可选，用于本次生成时给大模型的额外提示词。
- `force=true` 时，即使当前已有 revise 结果，也重新生成并覆盖。
- 接口会先落一份 `status=generating` 的 revision，并用原句创建初始 span items。
- 重新生成时会清空当前 revision items 上已有的 `draft_text / draft_cue`。
- 后台线程继续执行 LLM 任务；前端应轮询 `GET /revisions`。

### 2) `GET /revisions?session_id={session_id}`

返回当前 session 对应的 revision。

`status_name` 可能值：
- `pending`
- `generating`
- `completed`
- `failed`

在 `generating` 期间：
- 已完成的 segment 会返回真实 revise span
- 未完成的部分仍返回原句占位 span

### 3) `PATCH /revisions/items/{item_id}`

请求体：

```json
{
  "draft_text": "I just need some free time to work on my own projects.",
  "draft_cue": "[用轻松但有点无奈的语气说]"
}
```

行为约束：
- `draft_text` / `draft_cue` 保存用户编辑后的当前版本。
- 前端展示时优先使用 `draft_*`，为空时回退到 `suggested_*`。
- `item_id` 对应的是一个 revise span，不一定只覆盖一个 utterance。

## Span Item 数据结构

当前 revision item 关键字段：

- `source_seq_start`: span 起始 utterance seq
- `source_seq_end`: span 结束 utterance seq
- `source_seq_count`: span 内包含多少个 utterance
- `source_seqs`: 完整的 source seq 列表，例如 `[4]` 或 `[4, 5]`
- `original_text`: span 内原始 utterance 文本拼接结果
- `suggested_text`: LLM 产出的 revise 文本
- `suggested_cue`: LLM 产出的表达提示
- `draft_text` / `draft_cue`: 用户编辑态

示例：

```json
{
  "item_id": "4b0cbfc2-36f3-42d1-93ef-5fdf80c21149",
  "source_seq_start": 4,
  "source_seq_end": 5,
  "source_seq_count": 2,
  "source_seqs": [4, 5],
  "original_text": "See, you can. I can't.",
  "suggested_text": "Look, you've got the time for that, but I don't.",
  "suggested_cue": "带点无奈又吐槽的语气，对比自己和对方的情况。",
  "score": 60,
  "issue_tags": "表意不明, 衔接不连贯",
  "explanations": "原始两句被切得太碎，合并后更符合自然口语。"
}
```

约束：
- `source_seqs` 必须非空、连续。
- 一个 target utterance 在同一 revision 中必须被覆盖且只能被覆盖一次。
- 只允许合并相邻 utterance。
- 不允许跨 speaker 合并。

## LLM 生成流程

当前 `llm_provider.py` 的主流程：

1. 读取整段 transcript。
2. 先调用一次 LLM 生成章节总结和分段计划。
3. 每段带少量前后文并发调用 LLM 执行 revise。
4. LLM 对每段返回 `items[].source_seqs + suggested_* + score + issue_tags + explanations`。
5. 后端校验：
   - `source_seqs` 是否连续
   - 是否覆盖全部 target utterance
   - 是否有 gaps / overlaps
   - 是否跨 speaker 合并
   - `suggested_text` 是否为空
6. 每完成一段就增量写回数据库。
7. 全部完成后把 revision 状态置为 `completed`；失败则置为 `failed`。

提示词里只会把 `addions` 里的 `emotion` 和 `emotion_degree` 发给模型，其他附加字段不会进入 revise prompt。

## 模块结构

```text
revision/
|- api.py
|- service.py
|- repo.py
|- model.py
|- schema.py
|- types.py
|- llm_provider.py
|- README.md
```

## 数据库

下面这段是当前 span item 结构的干净建表 SQL，可以直接执行：

```sql
CREATE TABLE IF NOT EXISTS public.utterances_revisions (
    revision_id       UUID PRIMARY KEY,
    session_id        UUID NOT NULL,
    task_id           UUID NOT NULL,
    user_prompt       TEXT,
    x_status          SMALLINT NOT NULL DEFAULT 0,
    error_code        VARCHAR(64),
    error_message     TEXT,
    item_count        INTEGER NOT NULL DEFAULT 0,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_utterances_revisions_session_id
    ON public.utterances_revisions (session_id);

CREATE TABLE IF NOT EXISTS public.utterances_revision_items (
    item_id             UUID PRIMARY KEY,
    revision_id         UUID NOT NULL,
    task_id             UUID NOT NULL,
    source_seq_start    INTEGER NOT NULL,
    source_seq_end      INTEGER NOT NULL,
    source_seq_count    INTEGER NOT NULL,
    source_seqs         JSONB NOT NULL DEFAULT '[]'::jsonb,
    speaker             VARCHAR(64),
    start_time          INTEGER NOT NULL,
    end_time            INTEGER NOT NULL,
    original_text       TEXT NOT NULL,
    suggested_text      TEXT NOT NULL,
    suggested_cue       TEXT,
    draft_text          TEXT,
    draft_cue           TEXT,
    score               SMALLINT NOT NULL,
    issue_tags          TEXT NOT NULL DEFAULT '',
    explanations        TEXT NOT NULL DEFAULT '',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_utterances_revision_items_revision_seq_span
    ON public.utterances_revision_items (revision_id, source_seq_start, source_seq_end);

CREATE INDEX IF NOT EXISTS idx_utterances_revision_items_task_seq_span
    ON public.utterances_revision_items (task_id, source_seq_start, source_seq_end);

CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_utterances_revisions_set_updated_at
    ON public.utterances_revisions;

DROP TRIGGER IF EXISTS trg_utterances_revision_items_set_updated_at
    ON public.utterances_revision_items;

CREATE TRIGGER trg_utterances_revisions_set_updated_at
BEFORE UPDATE ON public.utterances_revisions
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_utterances_revision_items_set_updated_at
BEFORE UPDATE ON public.utterances_revision_items
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();
```

## 前端展示约定

推荐前端取值规则：

```text
display_text = draft_text ?? suggested_text
display_cue  = draft_cue ?? suggested_cue
```

页面展示建议：
- 按 `source_seq_start, source_seq_end` 排序
- 单句 span 显示 `#12`
- 合并 span 显示 `#12-13`
- `source_seq_count > 1` 时显示 merged 标记
- 原音频播放使用 span 的 `start_time ~ end_time`

## Cue 高亮输入

- Revise 编辑框里，cue 仍然作为可编辑纯文本的一部分保存，约定格式为任意数量的 `[cue]` 片段夹在正文中。
- 原生 `textarea` 不能对局部文本单独着色，所以前端采用“双层输入框”：
  - 底层是 mirror `div`，按正则匹配 `[ ... ]` 片段并高亮；
  - 顶层是原生 `textarea`，负责输入、光标、选区、输入法和复制粘贴。
- 语音合成或导出纯句子时，需要先剥掉所有 `[ ... ]` cue 片段，再压缩多余空白。

## 设计取舍

- 当前阶段不保存历史 revision，只保留当前结果。
- `suggested_*` 与 `draft_*` 分开保存，便于保留模型原始产物，同时支持用户编辑态。
- 选择 span item 而不是单句 item，是为了让模型能合法表达 ASR 碎句合并，而不是通过空 `suggested_text` 隐式处理。
