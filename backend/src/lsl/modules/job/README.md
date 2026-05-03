# LSL - Job Module

Job 模块负责通用异步任务生命周期，不承载具体业务结果。

## 模块职责

- 创建和查询异步 `job`
- 管理状态流转：`queued -> running -> completed/failed/canceled`
- 支持轻量进度、错误、下次运行时间和 worker lock
- 按 `job_type` 分发到业务模块注册的 `JobHandler`

业务结果仍由所属模块保存。例如：

- ASR 任务完成后写 transcript 相关表
- AI script 生成完成后写 script / transcript 相关表
- TTS 合成完成后写 tts synthesis / asset 相关表

## 状态码

- `0`：queued
- `1`：running
- `2`：completed
- `3`：failed
- `4`：canceled

## 分发模型

Job 模块不 import 具体业务模块。启动时由 `main.py` 或组合层注册 handler：

```python
job_service.register_handler(asr_job_handler)
job_service.register_handler(script_job_handler)
job_service.register_handler(tts_job_handler)
```

运行时：

```text
job_runner
-> claim due jobs
-> find handler by job_type
-> handler writes domain tables
-> JobService marks job status
```

服务启动后，`main.py` 会在 FastAPI lifespan 中启动一个后台 scheduler：

- scheduler 用协程定时 claim due jobs。
- 已 claim 的 job 交给固定大小线程池执行，避免阻塞主事件循环。
- 同一轮最多 claim `JOB_RUNNER_BATCH_SIZE` 个 job，同时最多执行 `JOB_RUNNER_MAX_WORKERS` 个 job。
- `POST /jobs/run-due` 保留为本地调试入口。

## Runner 配置

```env
JOB_RUNNER_ENABLED=true
JOB_RUNNER_INTERVAL_SECONDS=2
JOB_RUNNER_BATCH_SIZE=10
JOB_RUNNER_MAX_WORKERS=4
```

## 当前接口

- `POST /jobs` 创建 job
- `GET /jobs/{job_id}` 查询 job
- `GET /jobs` 查询 job 列表
- `POST /jobs/{job_id}/run` 调试运行单个 job
- `POST /jobs/run-due` 调试运行到期 job

## 建表 SQL

```sql
CREATE TABLE IF NOT EXISTS public.job_jobs (
    job_id        VARCHAR(32) PRIMARY KEY,
    job_type      VARCHAR(64) NOT NULL,
    x_status      SMALLINT NOT NULL DEFAULT 0,
    entity_type   VARCHAR(64),
    entity_id     VARCHAR(128),
    priority      INTEGER NOT NULL DEFAULT 0,
    progress      INTEGER NOT NULL DEFAULT 0,
    attempts      INTEGER NOT NULL DEFAULT 0,
    max_attempts  INTEGER NOT NULL DEFAULT 3,
    payload_json  TEXT NOT NULL DEFAULT '{}',
    result_json   TEXT,
    error_code    VARCHAR(64),
    error_message TEXT,
    locked_by     VARCHAR(128),
    locked_until  TIMESTAMPTZ,
    next_run_at   TIMESTAMPTZ,
    started_at    TIMESTAMPTZ,
    finished_at   TIMESTAMPTZ,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_job_jobs_status_next_run_at
    ON public.job_jobs (x_status, next_run_at);

CREATE INDEX IF NOT EXISTS idx_job_jobs_type_status_next_run_at
    ON public.job_jobs (job_type, x_status, next_run_at);

CREATE INDEX IF NOT EXISTS idx_job_jobs_entity
    ON public.job_jobs (entity_type, entity_id);

CREATE INDEX IF NOT EXISTS idx_job_jobs_created_at
    ON public.job_jobs (created_at);
```
