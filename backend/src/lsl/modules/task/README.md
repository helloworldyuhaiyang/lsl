# LSL - Task Module

Task 模块负责 ASR 任务编排，不直接依赖具体厂商实现。

## 当前实现

- `POST /tasks` 创建任务并触发 `asr_provider.submit`
- `GET /tasks/{task_id}` 查询任务（默认会自动尝试 refresh）
- `POST /tasks/{task_id}/refresh` 手动刷新任务状态
- `GET /tasks/{task_id}/transcript` 获取转写结果
- `GET /tasks` 查询任务列表

## 模块结构

```text
task/
|- api.py
|- service.py
|- repo.py
|- model.py
|- schema.py
|- types.py
|- asr_provider.py
|- asr/
|  |- __init__.py
|  |- fake_asr.py
|  `- volc_asr.py
|- result.json
```

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
    "audio_url": "https://your-bucket.oss-cn-hangzhou.aliyuncs.com/conversation/web_user/demo-audio.m4a",
    "language": "en-US"
  }'
```

如果本地有 `jq`，可直接提取 `task_id`：

```bash
TASK_ID=$(curl -s -X POST "$BASE_URL/tasks" \
  -H "Content-Type: application/json" \
  -d '{"object_key":"conversation/web_user/196f132e85f34227a6d7274dfb310b39.m4a","audio_url":"https://your-bucket.oss-cn-hangzhou.aliyuncs.com/conversation/web_user/196f132e85f34227a6d7274dfb310b39.m4a","language":"en-US"}' \
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
-- 任务主表：记录 ASR 调度状态与 provider 元数据
CREATE TABLE IF NOT EXISTS public.tasks (
    task_id               UUID PRIMARY KEY,                        -- 任务唯一 ID
    object_key            TEXT NOT NULL UNIQUE,                    -- 音频对象键（同一音频幂等）
    audio_url             TEXT NOT NULL,                           -- 音频可访问 URL
    x_duration_ms         INTEGER,                                 -- 冗余总时长（毫秒）
    x_status              SMALLINT NOT NULL DEFAULT 0 CHECK (x_status IN (0,1,2,3,4)), -- 状态码
    x_language            VARCHAR(16),                             -- 语种
    x_provider            VARCHAR(32) NOT NULL DEFAULT 'noop',     -- ASR 提供方
    x_provider_request_id VARCHAR(128),                            -- provider 请求 ID
    x_provider_resource_id VARCHAR(64),                            -- provider 资源 ID
    x_tt_logid            VARCHAR(128),                            -- provider 链路日志 ID
    x_provider_status_code VARCHAR(32),                            -- provider 状态码
    x_provider_message    TEXT,                                    -- provider 原始消息
    error_code            VARCHAR(64),                             -- 业务错误码
    error_message         TEXT,                                    -- 业务错误消息
    poll_count            INTEGER NOT NULL DEFAULT 0,              -- 已轮询次数
    last_polled_at        TIMESTAMPTZ,                             -- 最近轮询时间
    next_poll_at          TIMESTAMPTZ,                             -- 下次轮询时间
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),      -- 创建时间
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()       -- 更新时间
);

-- 轮询任务查询索引（按状态 + 下次轮询时间）
CREATE INDEX IF NOT EXISTS idx_tasks_status_next_poll_at
    ON public.tasks (x_status, next_poll_at);

-- 通用时间索引：任务列表倒序分页
CREATE INDEX IF NOT EXISTS idx_tasks_created_at
    ON public.tasks (created_at DESC);

-- ASR 结果主表：一条任务一份结构化结果
CREATE TABLE IF NOT EXISTS public.asr_results (
    task_id           UUID PRIMARY KEY REFERENCES public.tasks(task_id) ON DELETE CASCADE, -- 与任务 1:1
    x_provider        VARCHAR(32) NOT NULL,                      -- 实际使用的 provider
    duration_ms       INTEGER,                                   -- 音频总时长（毫秒）
    x_full_text       TEXT,                                      -- 全量拼接文本
    raw_result_json   JSONB NOT NULL,                            -- provider 原始回包
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()         -- 入库时间
);

-- ASR 分句表：保存每个分句的时间戳与说话人
CREATE TABLE IF NOT EXISTS public.asr_utterances (
    id               BIGSERIAL PRIMARY KEY,                      -- 自增主键
    task_id          UUID NOT NULL REFERENCES public.tasks(task_id) ON DELETE CASCADE, -- 关联任务
    seq              INTEGER NOT NULL,                           -- 句子序号（从 0 或 1 递增）
    x_text           TEXT NOT NULL,                              -- 分句文本
    speaker          VARCHAR(32),                                -- 说话人标识
    start_time       INTEGER NOT NULL,                           -- 开始时间（毫秒）
    end_time         INTEGER NOT NULL,                           -- 结束时间（毫秒）
    additions_json   JSONB NOT NULL DEFAULT '{}'::jsonb,         -- 扩展字段
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),         -- 创建时间
    CONSTRAINT uq_asr_utterance_task_seq UNIQUE (task_id, seq)   -- 同一任务内 seq 唯一
);

-- 分句读取索引：按任务顺序读取转写文本
CREATE INDEX IF NOT EXISTS idx_asr_utterances_task_id
    ON public.asr_utterances (task_id, seq);

-- 统一更新时间函数：每次 UPDATE 自动刷新 updated_at
CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 幂等创建触发器前先删除旧触发器
DROP TRIGGER IF EXISTS trg_tasks_set_updated_at ON public.tasks;

-- 更新前触发：自动维护 tasks.updated_at
CREATE TRIGGER trg_tasks_set_updated_at
BEFORE UPDATE ON public.tasks
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();
```
