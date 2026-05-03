# LSL - TTS Module

TTS 模块负责当前脚本的语音合成、speaker 映射、试听缓存和整段音频资产落库。

当前设计包含两个粒度：

- item 级试听：`revise-page` 上单条 revise span 的 `Synthesize`
- session 级整段音频：`Synthesize All` 后生成当前 session 的 listening material

## 设计原则

- 接口归 `tts` 模块所有。
- TtsService 只依赖脚本源、会话信息、缓存和资产能力，不直接暴露上游模块内部字段。
- TTS 的最小生成单元是脚本 item，不是原始 utterance。
- TTS 只接收解析后的脚本内容 `content`。
- 每个 `session` 只保留一份当前整段 TTS 结果，不保存历史版本。
- 单句试听使用 Redis 缓存音频 bytes，整段音频上传到 asset 并持久化。
- speaker 映射按 session 维度保存：`conversation_speaker -> provider_speaker_id`。

## 当前接口设计

- `GET /tts/providers/{provider}/speakers` 获取 provider 可用 speaker 列表
- `GET /tts/settings?session_id={session_id}` 获取当前 session 的 TTS 设置
- `PUT /tts/settings` 保存当前 session 的 TTS 设置和 speaker 映射
- `POST /tts/items/{item_id}/generate` 生成或复用单条试听音频
- `POST /tts` 批量生成当前 session 的整段 TTS
- `GET /tts?session_id={session_id}` 查询当前 session 的整段 TTS 结果

## ID 规范

- 对外 `synthesis_id` 格式约定为 `tts_{uuidhex}`，例如 `tts_196f132e85f34227a6d7274dfb310b39`。
- 当前数据库内部实际存的是 32 位无横线十六进制字符串；`synthesis_id` 对外返回时会再拼上 `tts_` 前缀。

## 环境变量

```env
TTS_PROVIDER=noop

TTS_REDIS_URL=redis://127.0.0.1:6379/0
TTS_CACHE_TTL_SECONDS=7200

TTS_VOLC_APP_ID=
TTS_VOLC_ACCESS_KEY=
TTS_VOLC_RESOURCE_ID=seed-tts-2.0
TTS_VOLC_URL=https://openspeech.bytedance.com/api/v3/tts/unidirectional
TTS_VOLC_HTTP_TIMEOUT=60

TTS_DEFAULT_FORMAT=mp3
TTS_DEFAULT_EMOTION_SCALE=4.0
TTS_DEFAULT_SPEECH_RATE=0.0
TTS_DEFAULT_LOUDNESS_RATE=0.0
```

说明：

- `TTS_PROVIDER=noop` 时，调用接口直接返回未实现错误。
- `TTS_PROVIDER=fake` 时，返回固定测试音频，便于联调。
- `TTS_PROVIDER=volc` 时，走火山 HTTP 流式 TTS。
- `TTS_CACHE_TTL_SECONDS=7200` 表示试听 clip 在 Redis 中保留 2 小时。

## 接口语义

### 1) `GET /tts/providers/{provider}/speakers`

返回当前 provider 可用的 speaker 列表。

返回项建议字段：

- `speaker_id`
- `name`
- `language`
- `gender`
- `style`
- `description`

示例：

```json
{
  "items": [
    {
      "speaker_id": "en_female_story_v1",
      "name": "English Female Story",
      "language": "en",
      "gender": "female",
      "style": "natural",
      "description": "适合英语口语对话和听力材料"
    }
  ]
}
```

### 2) `GET /tts/settings?session_id={session_id}`

返回当前 session 的 TTS 设置。

返回字段建议：

- `session_id`
- `format`
- `emotion_scale`
- `speech_rate`
- `loudness_rate`
- `speaker_mappings`

其中 `speaker_mappings` 示例：

```json
[
  {
    "conversation_speaker": "user-1",
    "provider_speaker_id": "en_male_conversation_v1"
  },
  {
    "conversation_speaker": "user-2",
    "provider_speaker_id": "en_female_story_v1"
  }
]
```

### 3) `PUT /tts/settings`

保存当前 session 的 TTS 设置和 speaker 映射。

请求体：

```json
{
  "session_id": "8f85f0be-6f53-4ca4-b6fe-b5d3f0a64047",
  "format": "mp3",
  "emotion_scale": 4.0,
  "speech_rate": 0.0,
  "loudness_rate": 0.0,
  "speaker_mappings": [
    {
      "conversation_speaker": "user-1",
      "provider_speaker_id": "en_male_conversation_v1"
    },
    {
      "conversation_speaker": "user-2",
      "provider_speaker_id": "en_female_story_v1"
    }
  ]
}
```

行为约束：

- `session_id` 必填。
- `format` 必填。
- `speaker_mappings[].conversation_speaker` 在同一 session 内必须唯一。
- 火山 V3 参数范围：`emotion_scale` 为 1 到 5，`speech_rate` 为 -50 到 100，`loudness_rate` 为 -50 到 100。

### 4) `POST /tts/items/{item_id}/generate`

生成或复用单条试听音频。

请求体：

```json
{
  "session_id": "8f85f0be-6f53-4ca4-b6fe-b5d3f0a64047",
  "content": "[用轻松但有点无奈的语气说] I just need some free time to work on my own projects.",
  "force": false
}
```

行为约束：

- `item_id` 对应当前脚本 item。
- `content` 必填，且不能为空。
- 后端从 `content` 中提取 `cue_texts`，剥离后得到 `plain_text`。
- 根据 `plain_text + cue_texts + provider + provider_speaker_id + format + emotion_scale + speech_rate + loudness_rate` 计算 `content_hash`。
- 生成前先查 Redis 缓存；命中则直接返回缓存音频。
- `force=true` 时忽略缓存重生成。

返回约定：

- 直接返回音频流
- `Content-Type: audio/mpeg`

### 5) `POST /tts`

为当前 session 批量生成整段 TTS。

请求体：

```json
{
  "session_id": "8f85f0be-6f53-4ca4-b6fe-b5d3f0a64047",
  "force": false
}
```

行为约束：

- 依赖当前 session 必须已有可合成脚本。
- 批量生成单位是当前脚本的 items，按顺序排序。
- 每条 item 先尝试复用 Redis clip 缓存；未命中时再调 provider。
- 所有 item clip 生成后，按顺序拼接成整段音频。
- 整段音频上传到 asset，并写入当前 synthesis 主记录。
- `force=true` 时忽略当前整段结果并重跑。
- 接口先返回 `status=generating`，后台继续执行；前端轮询 `GET /tts`。

### 6) `GET /tts?session_id={session_id}`

返回当前 session 的整段 TTS 结果。

`status_name` 可能值：

- `pending`
- `generating`
- `completed`
- `partial`
- `failed`

返回字段建议：

- `synthesis_id`
- `session_id`
- `provider`
- `full_asset_url`
- `full_duration_ms`
- `item_count`
- `completed_item_count`
- `failed_item_count`
- `status_name`
- `items`

`items[]` 建议字段：

- `item_id`
- `conversation_speaker`
- `provider_speaker_id`
- `content`
- `plain_text`
- `cue_texts`
- `content_hash`
- `duration_ms`
- `status_name`

## 文本规范化

TTS 输入统一叫 `content`。

解析规则：

1. `content` 允许内嵌任意数量的 `[cue]` 片段。
2. 把所有 `[ ... ]` 片段提取为 `cue_texts`。
3. 删除这些片段并压缩多余空白后得到 `plain_text`。
4. `plain_text` 为空时禁止发起 TTS。

示例：

```text
content = "[用轻松但有点无奈的语气说] I just need some free time to work on my own projects."

cue_texts  = ["用轻松但有点无奈的语气说"]
plain_text = "I just need some free time to work on my own projects."
```

provider 请求时：

- `plain_text` 作为真正的朗读文本
- `cue_texts` 映射到 provider 的风格控制参数，例如 `context_texts`

## 缓存设计

试听 clip 使用 Redis 缓存，键格式：

```text
tts:clip:{provider}:{content_hash}
```

缓存值：

- 音频 bytes
- `content_type`
- `duration_ms`
- `provider_speaker_id`

约束：

- `content_hash` 使用 `sha256`。
- `content_hash` 计算输入必须包含：
  - `plain_text`
  - `cue_texts`
  - `provider`
  - `provider_speaker_id`
  - `format`
  - `emotion_scale`
  - `speech_rate`
  - `loudness_rate`
- Redis 只缓存试听 clip，不作为整段音频的最终存储。
- Redis 的读取过程不对前端暴露，接口内部优先查缓存。

## 模块结构

```text
tts/
|- api.py
|- service.py
|- repo.py
|- model.py
|- schema.py
|- types.py
|- cache.py
|- provider.py
|- providers/
|  |- __init__.py
|  |- fake_tts.py
|  `- volc_tts.py
|- README.md
|- tts_http_demo.py
```

## 建表 SQL

默认本地运行使用 `SQLite` 并由 SQLAlchemy 自动建表；下面这份 SQL 主要用于手动初始化 `PostgreSQL`。

```sql
-- session 级 TTS 设置：保存合成参数和 speaker 映射
CREATE TABLE IF NOT EXISTS public.tts_session_settings (
    session_id              VARCHAR(32) PRIMARY KEY,               -- 会话 ID（uuid hex）
    x_format                VARCHAR(16) NOT NULL DEFAULT 'mp3',   -- 输出格式
    emotion_scale           NUMERIC NOT NULL DEFAULT 4.0,         -- 情感强度
    speech_rate             NUMERIC NOT NULL DEFAULT 0.0,         -- 语速
    loudness_rate           NUMERIC NOT NULL DEFAULT 0.0,         -- 音量
    speaker_mappings_json   TEXT NOT NULL DEFAULT '[]',           -- speaker 映射数组 JSON 字符串
    created_at              TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP, -- 创建时间
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP -- 更新时间
);

-- 当前 session 的整段 TTS 结果
CREATE TABLE IF NOT EXISTS public.tts_syntheses (
    synthesis_id           VARCHAR(32) PRIMARY KEY,                -- 合成主键（uuid hex）
    session_id             VARCHAR(32) NOT NULL UNIQUE,            -- 一次 session 只保留当前结果
    x_provider             VARCHAR(32) NOT NULL,                   -- 实际使用的 provider
    full_content_hash      VARCHAR(64) NOT NULL,                   -- 整段脚本 hash
    full_asset_object_key  TEXT,                                   -- 最终整段音频 object_key
    full_duration_ms       INTEGER,                                -- 最终整段时长
    item_count             INTEGER NOT NULL DEFAULT 0,             -- item 总数
    completed_item_count   INTEGER NOT NULL DEFAULT 0,             -- 已完成 item 数
    failed_item_count      INTEGER NOT NULL DEFAULT 0,             -- 失败 item 数
    x_status               SMALLINT NOT NULL DEFAULT 0,            -- 状态码
    error_code             VARCHAR(64),                            -- 错误码
    error_message          TEXT,                                   -- 错误信息
    created_at             TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP, -- 创建时间
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP -- 更新时间
);

CREATE INDEX IF NOT EXISTS idx_tts_syntheses_session_created_at
    ON public.tts_syntheses (session_id, created_at DESC);

-- item 级 TTS 快照：一个脚本 item 对应一条
CREATE TABLE IF NOT EXISTS public.tts_synthesis_items (
    tts_item_id           VARCHAR(32) PRIMARY KEY,                 -- item 主键（uuid hex）
    synthesis_id          VARCHAR(32) NOT NULL,                    -- 关联 synthesis
    source_item_id        VARCHAR(32) NOT NULL,                    -- 对应脚本 item
    source_seq_start      INTEGER NOT NULL,                        -- span 起始 seq
    source_seq_end        INTEGER NOT NULL,                        -- span 结束 seq
    source_seqs           TEXT NOT NULL DEFAULT '[]',              -- 完整 seq 列表 JSON 字符串
    conversation_speaker  VARCHAR(64),                             -- 原对话 speaker
    provider_speaker_id   VARCHAR(128) NOT NULL,                   -- provider speaker
    content               TEXT NOT NULL,                           -- 输入内容
    plain_text            TEXT NOT NULL,                           -- 剥离 cue 后的正文
    cue_texts             TEXT NOT NULL DEFAULT '[]',              -- cue 列表 JSON 字符串
    content_hash          VARCHAR(64) NOT NULL,                    -- clip hash
    duration_ms           INTEGER,                                 -- clip 时长
    x_status              SMALLINT NOT NULL DEFAULT 0,             -- 状态码
    error_code            VARCHAR(64),                             -- 错误码
    error_message         TEXT,                                    -- 错误信息
    created_at            TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP, -- 创建时间
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP -- 更新时间
);

CREATE INDEX IF NOT EXISTS idx_tts_synthesis_items_seq_span
    ON public.tts_synthesis_items (synthesis_id, source_seq_start, source_seq_end);

CREATE UNIQUE INDEX IF NOT EXISTS uq_tts_synthesis_items_source_item
    ON public.tts_synthesis_items (synthesis_id, source_item_id);

-- 统一更新时间函数：每次 UPDATE 自动刷新 updated_at
CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_tts_session_settings_set_updated_at
    ON public.tts_session_settings;

DROP TRIGGER IF EXISTS trg_tts_syntheses_set_updated_at
    ON public.tts_syntheses;

DROP TRIGGER IF EXISTS trg_tts_synthesis_items_set_updated_at
    ON public.tts_synthesis_items;

CREATE TRIGGER trg_tts_session_settings_set_updated_at
BEFORE UPDATE ON public.tts_session_settings
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_tts_syntheses_set_updated_at
BEFORE UPDATE ON public.tts_syntheses
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_tts_synthesis_items_set_updated_at
BEFORE UPDATE ON public.tts_synthesis_items
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();
```

状态码约定：

- `0` pending
- `1` generating
- `2` completed
- `3` partial
- `4` failed

## 前端约定

- `revise-page` 单条 `Synthesize`：
  - 调 `POST /tts/items/{item_id}/generate`
  - 直接播放返回的音频流
- `revise-page` 的 `Synthesize All`：
  - 先保存当前页面草稿
  - 再调 `POST /tts`
- `listening-page`：
  - 调 `GET /tts?session_id=...`
  - 优先使用 `full_asset_url`
- speaker 映射面板：
  - 先调 `GET /tts/providers/{provider}/speakers`
  - 再调 `GET /tts/settings`
  - 保存时调 `PUT /tts/settings`
