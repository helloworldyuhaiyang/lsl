# LSL - Task Module

Task 模块负责 ASR 任务编排，不直接依赖具体厂商实现。

## 当前实现

- `POST /tasks` 创建任务并触发 `asr_provider.submit`
- `GET /tasks/{task_id}` 查询任务（默认会自动尝试 refresh）
- `POST /tasks/{task_id}/refresh` 手动刷新任务状态
- `GET /tasks/{task_id}/transcript` 获取转写结果
- `GET /tasks` 查询任务列表

## 接口测试（curl）

先设置基础地址：

```bash
BASE_URL="http://127.0.0.1:8000"
```

1) 创建任务（`POST /tasks`）

```bash
curl -s -X POST "$BASE_URL/tasks" \
  -H "Content-Type: application/json" \
  -d '{
    "object_key": "conversation/web_user/demo-audio.m4a",
    "language": "en-US"
  }'
```

如果本地有 `jq`，可直接提取 `task_id`：

```bash
TASK_ID=$(curl -s -X POST "$BASE_URL/tasks" \
  -H "Content-Type: application/json" \
  -d '{"object_key":"conversation/web_user/demo-audio.m4a","language":"en-US"}' \
  | jq -r '.data.task_id')
echo "$TASK_ID"
```

2) 查询任务详情（`GET /tasks/{task_id}`）

```bash
curl -s "$BASE_URL/tasks/$TASK_ID"
```

3) 手动刷新任务状态（`POST /tasks/{task_id}/refresh`）

```bash
curl -s -X POST "$BASE_URL/tasks/$TASK_ID/refresh"
```

4) 获取转写结果（`GET /tasks/{task_id}/transcript`）

```bash
curl -s "$BASE_URL/tasks/$TASK_ID/transcript"
```

附：需要原始结果时带 `include_raw=true`：

```bash
curl -s "$BASE_URL/tasks/$TASK_ID/transcript?include_raw=true"
```

5) 任务列表（`GET /tasks`）

```bash
curl -s "$BASE_URL/tasks?limit=20"
```

按状态过滤（`transcribing=1`、`completed=3`）：

```bash
curl -s "$BASE_URL/tasks?limit=20&status=3"
```

## 建表 SQL

```sql
CREATE TABLE IF NOT EXISTS public.tasks (
    task_id               UUID PRIMARY KEY,
    object_key            TEXT NOT NULL UNIQUE,
    x_status              SMALLINT NOT NULL DEFAULT 0 CHECK (x_status IN (0,1,2,3,4)),
    x_language            VARCHAR(16),
    x_provider            VARCHAR(32) NOT NULL DEFAULT 'noop',
    x_provider_request_id VARCHAR(128),
    x_provider_resource_id VARCHAR(64),
    x_tt_logid            VARCHAR(128),
    x_provider_status_code VARCHAR(32),
    x_provider_message    TEXT,
    error_code            VARCHAR(64),
    error_message         TEXT,
    poll_count            INTEGER NOT NULL DEFAULT 0,
    last_polled_at        TIMESTAMPTZ,
    next_poll_at          TIMESTAMPTZ,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tasks_status_next_poll_at
    ON public.tasks (x_status, next_poll_at);

CREATE INDEX IF NOT EXISTS idx_tasks_created_at
    ON public.tasks (created_at DESC);

CREATE TABLE IF NOT EXISTS public.asr_results (
    task_id           UUID PRIMARY KEY REFERENCES public.tasks(task_id) ON DELETE CASCADE,
    x_provider        VARCHAR(32) NOT NULL,
    duration_ms       INTEGER,
    x_full_text       TEXT,
    raw_result_json   JSONB NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.asr_utterances (
    id               BIGSERIAL PRIMARY KEY,
    task_id          UUID NOT NULL REFERENCES public.tasks(task_id) ON DELETE CASCADE,
    seq              INTEGER NOT NULL,
    x_text           TEXT NOT NULL,
    speaker          VARCHAR(32),
    start_time       INTEGER NOT NULL,
    end_time         INTEGER NOT NULL,
    additions_json   JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_asr_utterance_task_seq UNIQUE (task_id, seq)
);

CREATE INDEX IF NOT EXISTS idx_asr_utterances_task_id
    ON public.asr_utterances (task_id, seq);

CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_tasks_set_updated_at ON public.tasks;

CREATE TRIGGER trg_tasks_set_updated_at
BEFORE UPDATE ON public.tasks
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();
```
