# LSL - Session Module

Session 模块负责会话级数据管理（标题、描述）以及与 `assets/tasks` 的关联。

设计原则：
- `sessions` 不冗余 `tasks/assets` 业务字段。
- 模块交互通过 Service 依赖：`SessionService -> AssetService/TaskService`。
- SessionRepository 只访问 `public.sessions` 表，不直接读 `assets/tasks`。
- Repository 使用 SQLAlchemy 2.0 ORM，Service 直接消费模型对象。

## 当前接口

- `POST /sessions` 创建会话
- `GET /sessions` 查询会话列表
- `GET /sessions/{session_id}` 查询会话详情
- `PATCH /sessions/{session_id}` 更新会话与关联关系

## ID 规范

- 对外 `session_id` 格式约定为 `s_{uuid}`，例如 `s_8f85f0be-6f53-4ca4-b6fe-b5d3f0a64047`。
- 引用 task 时，对外 `current_task_id` 也应使用 `t_{uuid}`。
- 当前 README 下方建表 SQL 仍以裸 `UUID` 为例；如果要按此前缀落地，需要同步调整表结构与仓储层校验逻辑。

## 模块结构

```text
session/
|- api.py
|- service.py
|- repo.py
|- model.py
|- schema.py
|- types.py
```

## 建表 SQL

```sql
-- 会话主表：管理会话标题/描述与资产、任务关联
CREATE TABLE IF NOT EXISTS public.sessions (
    session_id        UUID PRIMARY KEY,                           -- 会话主键
    title             VARCHAR(200) NOT NULL,                      -- 会话标题
    f_desc            TEXT,                                       -- 会话描述
    f_language        VARCHAR(16),                                -- 会话语言（可选）
    f_type            SMALLINT NOT NULL DEFAULT 1 CHECK (f_type IN (1, 2)), -- 会话类型：1录音/2文本
    asset_object_key  TEXT UNIQUE,                                -- 关联资产 object_key（可空）
    current_task_id   UUID UNIQUE,                                -- 关联任务 ID（可空）
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),         -- 创建时间
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),         -- 更新时间

    -- 标题去空格后不能为空
    CONSTRAINT ck_sessions_title_non_empty
        CHECK (length(btrim(title)) > 0),

    -- 资产外键：资产删除后会话置空
    CONSTRAINT fk_sessions_asset_object_key
        FOREIGN KEY (asset_object_key)
        REFERENCES public.assets(object_key)
        ON DELETE SET NULL,

    -- 任务外键：任务删除后会话置空
    CONSTRAINT fk_sessions_current_task_id
        FOREIGN KEY (current_task_id)
        REFERENCES public.tasks(task_id)
        ON DELETE SET NULL
);

-- 列表页常用索引：按创建时间倒序分页
CREATE INDEX IF NOT EXISTS idx_sessions_created_at
    ON public.sessions (created_at DESC);

-- 标题模糊搜索索引（lower）
CREATE INDEX IF NOT EXISTS idx_sessions_title_lower
    ON public.sessions (lower(title));

-- 更新前触发：自动维护 updated_at（依赖 public.set_updated_at 函数）
CREATE TRIGGER trg_sessions_set_updated_at
BEFORE UPDATE ON public.sessions
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();
```

`f_type` 语义：
- `1`：录音 Session（需要音频：`asset_object_key` 或 `current_task_id`）
- `2`：文本 Session（不需要上传文件）
