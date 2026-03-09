# LSL - Revision Module

Revision 模块负责 utterance 级 revise 生成、打分与用户编辑态保存。

设计原则：
- 接口归 `revision` 模块所有，不挂在 `session` 模块下。
- RevisionService 通过 `SessionService` 和 `TaskService` 获取 `session/task/transcript`，不跨模块直接访问别人的 repo。
- 当前阶段每个 `session` 只保留一份当前 revise 结果，不保存历史版本。
- 前端点击 `Revise` 按钮时，携带 `session_id + user_prompt` 触发整段 transcript 的 utterance 级重新生成，并重新打分。

## 当前接口设计

- `POST /revisions` 生成或覆盖当前 session 的 revise 结果
- `GET /revisions?session_id={session_id}` 查询当前 session 的 revise 结果
- `PATCH /revisions/items/{item_id}` 保存单条 revise 的用户编辑结果

## ID 规范

- 对外 `revision_id` 格式约定为 `r_{uuid}`，例如 `r_3d6fdd91-0d53-4491-a6b1-e8bcb52d18b4`。
- 引用 session 时，对外 `session_id` 使用 `s_{uuid}`；引用 task 时，对外 `task_id` 使用 `t_{uuid}`。
- 当前 README 下方建表 SQL 仍以裸 `UUID` 为例；如果要按此前缀落地，需要同步调整表结构与仓储层校验逻辑。

## 环境变量

```env
REVISION_PROVIDER=fake
REVISION_LLM_API_KEY=your-real-ark-api-key
REVISION_LLM_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
REVISION_LLM_MODEL=doubao-1-5-pro-32k-250115
REVISION_LLM_HTTP_TIMEOUT=120
```

说明：
- `REVISION_PROVIDER=fake` 时，RevisionService 返回固定 revise 文案，便于前后端联调。
- `REVISION_PROVIDER=ark` 时，RevisionService 会调用方舟大模型生成 utterance revise。
- 如果 provider 不可用或调用失败，服务会退回本地规则生成，保证接口仍可返回结果。

### 1) `POST /revisions`

请求体：

```json
{
  "session_id": "s_8f85f0be-6f53-4ca4-b6fe-b5d3f0a64047",
  "user_prompt": "请改成更自然、适合日常口语的表达",
  "force": true
}
```

行为约束：
- `session_id` 必填。
- `user_prompt` 可选，用于本次生成时给大模型的额外提示词。
- `force=true` 时，即使当前已有 revise 结果，也重新生成并覆盖。
- 当前阶段不保留历史版本；重新生成时直接覆盖 `utterances_revisions` 和 `utterances_revision_items`。

### 2) `GET /revisions?session_id={session_id}`

返回当前 session 对应的 revise 结果；如果尚未生成，则返回空结果或由 API 明确返回业务错误。

### 3) `PATCH /revisions/items/{item_id}`

请求体：

```json
{
  "draft_text": "I went to the park with my friends last weekend.",
  "draft_cue": "[自然的 / 轻松的 / 周末聊天]"
}
```

行为约束：
- `draft_text` / `draft_cue` 保存用户编辑后的当前版本。
- 前端展示时优先使用 `draft_*`，为空时回退到 `suggested_*`。

## 模块结构

```text
revision/
|- api.py
|- service.py
|- repo.py
|- model.py
|- schema.py
|- types.py
|- README.md
```

## 建表 SQL

```sql
-- revise 主表：每个 session 当前仅保留一份 revise 结果，不保存历史版本
CREATE TABLE IF NOT EXISTS public.utterances_revisions (
    revision_id       UUID PRIMARY KEY,                           -- revise 主键
    session_id        UUID NOT NULL,                              -- 对应 session
    task_id           UUID NOT NULL,                              -- 当前 revise 基于哪个 transcript/task 生成
    user_prompt       TEXT,                                       -- 用户本次点击 Revise 时输入的提示词
    x_status          SMALLINT NOT NULL DEFAULT 0,                -- revise 状态码：0 pending / 1 generating / 2 completed / 3 failed
    error_code        VARCHAR(64),                                -- 生成失败时的业务错误码
    error_message     TEXT,                                       -- 生成失败时的错误消息
    item_count        INTEGER NOT NULL DEFAULT 0,                 -- 当前生成出的 revise item 数量
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),         -- 创建时间
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()          -- 更新时间
);

-- 读取某个 session 当前 revise
CREATE INDEX IF NOT EXISTS idx_utterances_revisions_session_id
    ON public.utterances_revisions (session_id);

-- revise item 表：一条 transcript utterance 对应一条 revise 卡片
CREATE TABLE IF NOT EXISTS public.utterances_revision_items (
    item_id             UUID PRIMARY KEY,                         -- revise item 主键
    revision_id         UUID NOT NULL,                            -- 所属 revise 主表 ID
    task_id             UUID NOT NULL,                            -- 原 transcript 所属 task，用于定位原句
    utterance_seq       INTEGER NOT NULL,                         -- 原 utterance 序号，与 task_id 共同定位原句
    speaker             VARCHAR(64),                              -- 说话人标识
    start_time          INTEGER NOT NULL,                         -- 原句开始时间（毫秒）
    end_time            INTEGER NOT NULL,                         -- 原句结束时间（毫秒）
    original_text       TEXT NOT NULL,                            -- ASR 原句文本
    suggested_text      TEXT NOT NULL,                            -- 模型生成的建议文本（原始产物）
    suggested_cue       TEXT,                                     -- 模型生成的表达提示（原始产物）
    draft_text          TEXT,                                     -- 用户当前编辑后的文本；为空时前端回退 suggested_text
    draft_cue           TEXT,                                     -- 用户当前编辑后的 cue；为空时前端回退 suggested_cue
    score               SMALLINT NOT NULL,                        -- 当前句子的 revise 分数（0-100）
    issue_tags          TEXT NOT NULL DEFAULT '',                 -- 逗号分隔的问题标签，如 "语法错误, 不够自然"
    explanations        TEXT NOT NULL DEFAULT '',                 -- 当前句子的说明与修改建议
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),       -- 创建时间
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()        -- 更新时间
);

-- 某次 revise 内按 utterance 顺序读取卡片
CREATE INDEX IF NOT EXISTS idx_utterances_revision_items_revision_seq
    ON public.utterances_revision_items (revision_id, utterance_seq);

-- 通过 task_id + utterance_seq 追溯原句
CREATE INDEX IF NOT EXISTS idx_utterances_revision_items_task_seq
    ON public.utterances_revision_items (task_id, utterance_seq);

-- 统一更新时间函数：每次 UPDATE 自动刷新 updated_at
CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 幂等创建触发器前先删除旧触发器
DROP TRIGGER IF EXISTS trg_utterances_revisions_set_updated_at ON public.utterances_revisions;
DROP TRIGGER IF EXISTS trg_utterances_revision_items_set_updated_at ON public.utterances_revision_items;

-- 更新前触发：自动维护 updated_at
CREATE TRIGGER trg_utterances_revisions_set_updated_at
BEFORE UPDATE ON public.utterances_revisions
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_utterances_revision_items_set_updated_at
BEFORE UPDATE ON public.utterances_revision_items
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();
```

## 字段语义

- `suggested_text`：模型生成的建议文本，是 revise 的原始产物。
- `suggested_cue`：模型生成的表达提示，是 revise 的原始产物。
- `draft_text`：用户当前编辑后的文本；页面展示时优先使用它。
- `draft_cue`：用户当前编辑后的 cue；页面展示时优先使用它。

推荐前端取值规则：

```text
display_text = draft_text ?? suggested_text
display_cue  = draft_cue ?? suggested_cue
```

## 前端 Cue 高亮输入技巧

- Revise 编辑框里，cue 仍然作为可编辑纯文本的一部分保存，约定格式为任意数量的 `[cue]` 片段夹在正文中，例如：`[语气先压低一点] Suddenly, the curtain moved. [这里再紧一下] Who is there?`
- 原生 `textarea` 不能对局部文本单独着色，所以前端采用“双层输入框”：
  - 底层是一个 mirror `div`，按正则匹配所有 `[ ... ]` 片段，并把这些 cue 渲染成橙色；
  - 顶层仍然是原生 `textarea`，负责输入、光标、选区、输入法和复制粘贴，但文字本身设为透明，只显示底层 mirror 的内容。
- mirror 层与 `textarea` 必须保持相同的字体、行高、padding、换行规则，并同步 `scrollTop/scrollLeft`，否则高亮位置会错位。
- 语音合成或导出纯句子时，需要先把所有 `[ ... ]` cue 片段剥掉，再把多余空白压成单空格，避免 TTS 把 cue 文案读出来。

## 主流程

1. 用户在 Revise 页面输入 `user_prompt`，点击 `Revise` 按钮。
2. 前端调用 `POST /revisions`，提交 `session_id + user_prompt + force`。
3. RevisionService 通过 SessionService 获取当前 `session`，拿到 `current_task_id`。
4. RevisionService 通过 TaskService 获取 transcript utterances。
5. 服务把每条 utterance 连同上下文和 `user_prompt` 发送给 LLM，生成：
   - `suggested_text`
   - `suggested_cue`
   - `score`
   - `issue_tags`
   - `explanations`
6. 服务覆盖 `utterances_revisions` 主记录。
7. 服务删除该 `revision_id` 对应的旧 `utterances_revision_items`，插入新结果。
8. 前端重新读取 `GET /revisions?session_id={session_id}` 并渲染 revise cards。
9. 用户编辑某条 revise 后，前端调用 `PATCH /revisions/items/{item_id}` 持久化 `draft_*`。

## 设计取舍

- 当前阶段不保存历史生成结果，因此不需要 `is_current`、`version_no` 等字段。
- `task_id + utterance_seq` 保存在 item 表中，用于稳定定位原 transcript 原句。
- `suggested_*` 与 `draft_*` 分开保存，便于保留模型原始产物，同时支持用户编辑态。
