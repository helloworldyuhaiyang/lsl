# LSL - TTS Module

TTS 模块负责把 `revision` 模块产出的最终脚本文案转换成可播放音频，并把结果接入现有 `asset` 存储体系。

当前仓库里已经有一个厂商调用样例 [tts_http_demo.py](./tts_http_demo.py)，它证明“单次 HTTP 流式返回音频 bytes”是可行的；真正的模块设计重点不在 demo，而在下面这几个问题：

- 生成的音频如何和 `session / revision / asset` 关联
- revise 页的单句试听和 listening 页的整段训练音频如何共用一套后端能力
- 用户编辑 `draft_text` 后，哪些音频需要失效、哪些可以复用
- 厂商 TTS 本身没有“任务查询接口”时，系统自己的异步状态如何定义

## 模块职责

- 从当前 `session` 的当前 `revision` 读取最终展示脚本。
- 解析 `draft_text / suggested_text`，生成可合成的纯文本和风格提示。
- 调用具体 TTS provider 合成音频。
- 把音频保存为平台资产，并维护生成状态、缓存命中和错误信息。
- 对前端暴露稳定的“创建 / 查询 / 单条重生成”接口。



## 为什么要单独做一个 TTS 模块

推荐继续保持后端单向依赖：

`TTS API -> TtsService -> TtsRepository -> DB`

服务间依赖：

- `TtsService -> RevisionService`
- `TtsService -> SessionService`
- `TtsService -> AssetService`

不要让 `revision` 模块直接负责 TTS，原因是：

- TTS 需要独立缓存、状态机、provider 适配和存储上传。
- 前端后续会有两类 TTS 用法：
  - `revise-page` 的单句试听
  - `listening-page` 的整段训练材料

这两类场景共享同一类“语音资产”，但不应该污染 revision 的数据模型。

## 推荐分两期实现

### Phase 1: 单句试听先落地

目标：

- 替换 `revise-page` 里浏览器原生 `window.speechSynthesis`
- 用户点击某个 revise item 的 `Synthesize` 时，走后端生成真实音频
- 支持缓存复用和单条重生成

优点：

- 改动最小，能最快验证 provider、音质、延迟、存储链路
- 不需要先解决“整段拼接”或“多 speaker 不同声音”的复杂问题

### Phase 2: 整段 Listening Material

目标：

- 基于当前 revision 批量生成整段训练音频
- `listening-page` 优先展示 revised script + TTS 音频，而不是原始 transcript + 原录音

建议：
- 如果后续需要“一人一句不同 voice”，再升级为“逐条 clip 合成 + 服务端拼接”

## 当前前端和数据流的影响

当前 `revise-page` 的 `Synthesize` 按钮仍然调用浏览器本地语音合成，且 `listening-page` 读取的是原始 transcript。接入真实 TTS 后建议改成：

- `revise-page`
  - 单条 item 点击时调用 `POST /tts/items/{revision_item_id}/generate`
  - 返回 `asset_url`, 已有缓存使用缓存的 `asset_url`
- `listening-page`
  - 先取 `GET /tts?session_id=...`
  - 若存在 `completed` 的整段 TTS，则播放 `full_asset_url`
  - 文本展示使用 TTS snapshot 对应的 revised script

## 输入文本的规范化

TTS 输入必须以“当前用户看到的句子”为准，而不是单纯使用 `suggested_text`。

当前 revision 数据的真实情况是：

- 用户修改后，前端把整段可编辑内容直接写进 `draft_text`
- `draft_text` 里可能包含若干 `[cue]` 片段
- cue 直接内嵌在 `draft_text / suggested_text` 里，不再单独存字段

因此 TTS 模块建议定义统一解析规则：

1. 如果 `draft_text` 非空：
   - 从 `draft_text` 里提取所有 `[ ... ]` 片段，作为 `cue_texts`
   - 去掉这些 cue 后剩余正文，作为 `plain_text`
2. 否则：
   - `plain_text = suggested_text`
   - 从 `suggested_text` 里提取所有 `[ ... ]` 片段，作为 `cue_texts`
   - 去掉这些 cue 后剩余正文，作为 `plain_text`
3. `plain_text` 为空时禁止发起 TTS
4. `cue_texts` 不进入最终展示文本，但可以映射到 provider 的风格控制参数

示例：

```text
draft_text = "[用轻松但有点无奈的语气说] I just need some free time to work on my own projects."

cue_texts  = ["用轻松但有点无奈的语气说"]
plain_text = "I just need some free time to work on my own projects."
```

对于火山的 demo 接口，`cue_texts` 可以先映射到：

```json
{
  "additions": {
    "explicit_language": "en",
    "disable_markdown_filter": true,
    "context_texts": ["用轻松但有点无奈的语气说"]
  }
}
```

## Provider 设计

推荐仿照 `task/asr_provider.py` 做 provider 工厂，但接口形态不要照搬 ASR 的“submit + query”。

原因：

- 当前参考的 TTS HTTP 接口本质是“一次请求，流式返回音频块”
- 厂商侧没有独立 task id 供后续轮询
- 所以系统里的 `generating/completed/failed` 应该是 LSL 自己的后台任务状态，而不是 provider 原生状态

建议的领域协议：

```python
class TtsProvider(Protocol):
    def synthesize(self, req: TtsSynthesizeRequest) -> TtsSynthesizeResult:
        ...
```

请求对象建议字段：

- `session_id`
- `revision_id`
- `revision_item_id | None`
- `text`
- `cue_texts`
- `language`
- `voice_code`
- `audio_format`
- `sample_rate`
- `speech_rate`

返回对象建议字段：

- `audio_bytes`
- `content_type`
- `audio_format`
- `duration_ms | None`
- `provider_trace_id | None`
- `usage | dict | None`

推荐的 provider 列表：

- `fake`: 返回固定测试音频，先打通前后端
- `volc`: 对接当前 `tts_http_demo.py` 的真实实现
- `noop`: 明确报未实现

## 资产落库设计

这里有一个必须先补的基础能力：

当前 `asset` 模块只有“给前端生成 presigned upload url”的能力，但 TTS 是服务端自己拿到音频 bytes，必须能直接写对象存储。

所以推荐先扩展 `asset` 抽象：

- `StorageProvider.put_object_bytes(object_key, data, content_type) -> None`
- `AssetService.save_generated_asset(...) -> AssetListItemData | dict`

TTS 不直接操作 OSS SDK，而是仍然走 `AssetService`。

推荐的 object key：

- 单条 clip: `tts/{session_id}/{synthesis_id}/items/{seq_start}-{seq_end}-{content_hash[:12]}.mp3`
- 整段 full: `tts/{session_id}/{synthesis_id}/full-{content_hash[:12]}.mp3`

其中：

- `category = "tts"`
- `entity_id = session_id`

这样资产列表、清理脚本、CDN 路径都能继续复用现有约定。

## 数据模型设计

建议和 `revision` 一样，保存“当前 session 的当前 TTS 结果”，不做历史版本管理。

### 1) `speech_syntheses`

一条记录表示某个 session 当前的一次 TTS 结果集合。

建议字段：

- `synthesis_id UUID PRIMARY KEY`
- `session_id UUID NOT NULL UNIQUE`
- `revision_id UUID NOT NULL`
- `task_id UUID NOT NULL`
- `voice_code VARCHAR(128) NOT NULL`
- `audio_format VARCHAR(16) NOT NULL DEFAULT 'mp3'`
- `x_status SMALLINT NOT NULL DEFAULT 0`
- `item_count INTEGER NOT NULL DEFAULT 0`
- `completed_item_count INTEGER NOT NULL DEFAULT 0`
- `failed_item_count INTEGER NOT NULL DEFAULT 0`
- `full_asset_object_key TEXT`
- `full_duration_ms INTEGER`
- `error_code VARCHAR(64)`
- `error_message TEXT`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
- `updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`

状态建议：

- `0 pending`
- `1 generating`
- `2 completed`
- `3 partial`
- `4 failed`

### 2) `speech_synthesis_items`

一条记录对应一个 revision item 的语音快照。

建议字段：

- `tts_item_id UUID PRIMARY KEY`
- `synthesis_id UUID NOT NULL`
- `revision_item_id UUID NOT NULL`
- `source_seq_start INTEGER NOT NULL`
- `source_seq_end INTEGER NOT NULL`
- `source_seqs JSONB NOT NULL DEFAULT '[]'::jsonb`
- `speaker VARCHAR(64)`
- `display_text TEXT NOT NULL`
- `plain_text TEXT NOT NULL`
- `cue_texts JSONB NOT NULL DEFAULT '[]'::jsonb`
- `content_hash VARCHAR(64) NOT NULL`
- `voice_code VARCHAR(128) NOT NULL`
- `x_status SMALLINT NOT NULL DEFAULT 0`
- `asset_object_key TEXT`
- `duration_ms INTEGER`
- `provider_trace_id VARCHAR(128)`
- `error_code VARCHAR(64)`
- `error_message TEXT`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
- `updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`

约束建议：

- 同一 `synthesis_id + revision_item_id` 唯一
- `plain_text` 不能为空
- `content_hash` 基于 `plain_text + cue_texts + voice_code + audio_format` 计算

## SQL 草案

```sql
CREATE TABLE IF NOT EXISTS public.speech_syntheses (
    synthesis_id           UUID PRIMARY KEY,
    session_id             UUID NOT NULL UNIQUE,
    revision_id            UUID NOT NULL,
    task_id                UUID NOT NULL,
    voice_code             VARCHAR(128) NOT NULL,
    audio_format           VARCHAR(16) NOT NULL DEFAULT 'mp3',
    x_status               SMALLINT NOT NULL DEFAULT 0,
    item_count             INTEGER NOT NULL DEFAULT 0,
    completed_item_count   INTEGER NOT NULL DEFAULT 0,
    failed_item_count      INTEGER NOT NULL DEFAULT 0,
    full_asset_object_key  TEXT,
    full_duration_ms       INTEGER,
    error_code             VARCHAR(64),
    error_message          TEXT,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_speech_syntheses_revision_id
    ON public.speech_syntheses (revision_id);

CREATE TABLE IF NOT EXISTS public.speech_synthesis_items (
    tts_item_id        UUID PRIMARY KEY,
    synthesis_id       UUID NOT NULL,
    revision_item_id   UUID NOT NULL,
    source_seq_start   INTEGER NOT NULL,
    source_seq_end     INTEGER NOT NULL,
    source_seqs        JSONB NOT NULL DEFAULT '[]'::jsonb,
    speaker            VARCHAR(64),
    display_text       TEXT NOT NULL,
    plain_text         TEXT NOT NULL,
    cue_texts          JSONB NOT NULL DEFAULT '[]'::jsonb,
    content_hash       VARCHAR(64) NOT NULL,
    voice_code         VARCHAR(128) NOT NULL,
    x_status           SMALLINT NOT NULL DEFAULT 0,
    asset_object_key   TEXT,
    duration_ms        INTEGER,
    provider_trace_id  VARCHAR(128),
    error_code         VARCHAR(64),
    error_message      TEXT,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_speech_synthesis_items_revision_item
    ON public.speech_synthesis_items (synthesis_id, revision_item_id);

CREATE INDEX IF NOT EXISTS idx_speech_synthesis_items_seq_span
    ON public.speech_synthesis_items (synthesis_id, source_seq_start, source_seq_end);
```

## API 设计

### 1) `POST /tts`

作用：

- 为当前 session 的当前 revision 创建或刷新一份 TTS 任务
- 后台批量生成 clip，必要时生成 full audio

请求体建议：

```json
{
  "session_id": "8f85f0be-6f53-4ca4-b6fe-b5d3f0a64047",
  "voice_code": "en_female_story_v1",
  "force": false,
  "regenerate_stale_only": true,
  "include_full_audio": true
}
```

行为约束：

- 依赖当前 session 必须已有 revision
- `force=false` 且 revision_id / voice_code / content_hash 未变化时，直接返回已有结果
- `regenerate_stale_only=true` 时，仅重跑发生文本变化的 item
- 先落一份 `status=generating` 的 synthesis，再后台执行
- provider 调用失败时把单条 item 标为 `failed`，整批结果可落到 `partial`

### 2) `GET /tts?session_id={session_id}`

返回当前 session 的 TTS 结果。

返回字段建议包含：

- `status_name`
- `full_asset_url`
- `full_duration_ms`
- `items[]`
  - `revision_item_id`
  - `asset_url`
  - `status_name`
  - `plain_text`
  - `display_text`
  - `cue_texts`
  - `is_stale`

其中 `is_stale` 不必入库，可以在 service 层根据“当前 revision item 的最新 content_hash”和“tts item 的 content_hash”动态计算。

### 3) `POST /tts/items/{revision_item_id}/generate`

作用：

- revise 页单句试听专用
- 当前 item 没改过则直接复用缓存
- 当前 item 改过则仅重生成这一条

请求体建议：

```json
{
  "session_id": "8f85f0be-6f53-4ca4-b6fe-b5d3f0a64047",
  "voice_code": "en_female_story_v1",
  "force": false
}
```

推荐行为：

- 如果存在相同 `content_hash` 的完成结果，直接返回 `completed + asset_url`
- 否则创建或覆盖该 item 的当前 TTS 记录
- 这类单句请求可以直接同步执行，避免前端额外轮询

## Service 层主流程

### 批量合成

1. `TtsService.create_synthesis(session_id, ...)`
2. 通过 `SessionService` 确认 `session.current_task_id`
3. 通过 `RevisionService.get_revision(session_id)` 读取当前 revision
4. 把 revision items 规范化为 TTS snapshot items
5. 对每条 item 计算 `content_hash`
6. 保存 synthesis 主记录和 item 记录，状态置为 `generating`
7. 后台线程池逐条调用 provider
8. 每条成功后把音频写入 asset，并增量更新该 item
9. 全部 item 完成后：
   - 若需要 full audio，则生成整段音频并保存
   - 汇总状态为 `completed / partial / failed`

### 单句合成

1. 读取当前 revision item
2. 规范化文本并计算 `content_hash`
3. 若已有相同 hash 的 `completed` clip，直接返回
4. 否则调用 provider
5. 上传资产并保存 item 状态
6. 返回可播放 URL

## 配置设计

建议新增环境变量：

```env
TTS_PROVIDER=noop

TTS_VOLC_APP_ID=
TTS_VOLC_ACCESS_KEY=
TTS_VOLC_RESOURCE_ID=seed-tts-2.0
TTS_VOLC_URL=https://openspeech.bytedance.com/api/v3/tts/unidirectional
TTS_VOLC_HTTP_TIMEOUT=60

TTS_DEFAULT_VOICE=en_female_story_v1
TTS_DEFAULT_AUDIO_FORMAT=mp3
TTS_DEFAULT_SAMPLE_RATE=24000
TTS_DEFAULT_LANGUAGE=en
```

说明：

- `TTS_PROVIDER=fake` 时返回固定测试音频
- `TTS_PROVIDER=volc` 时走火山 HTTP 流式接口
- `TTS_DEFAULT_VOICE` 先做全局默认值，后续再扩展到按 speaker 映射

## 文件结构建议

```text
tts/
|- __init__.py
|- api.py
|- service.py
|- repo.py
|- model.py
|- schema.py
|- types.py
|- provider.py
|- providers/
|  |- __init__.py
|  |- fake_tts.py
|  |- volc_tts.py
|- README.md
|- tts_http_demo.py
```

说明：

- `tts_http_demo.py` 保留为调试样例，不参与正式模块装配
- 正式 provider 逻辑放到 `providers/volc_tts.py`

## 对当前项目最重要的几个设计结论

1. TTS 的源数据应该来自 `revision`，不是原始 transcript。
2. 单句试听和整段训练音频应该属于同一个 TTS 模块，只是粒度不同。
3. TTS 的异步状态机是“LSL 自己的后台任务状态”，不是厂商原生任务状态。
4. 要落地这个模块，必须先给 `asset` 增加“服务端直接上传 bytes”的能力。
5. 第一版推荐先做“单句试听 + 整段单 voice”，不要一开始就做多 speaker 拼接。

## 推荐实现顺序

1. 扩展 `asset` 模块，支持服务端写对象存储。
2. 新建 `tts/types.py` 和 provider 工厂，先接 `fake` / `noop`。
3. 把 `tts_http_demo.py` 收敛成正式的 `volc_tts.py` provider。
4. 实现 `POST /tts/items/{revision_item_id}/generate`，替换 revise 页本地合成。
5. 再实现 `POST /tts` + `GET /tts` 批量接口。
6. 最后把 `listening-page` 切到 revised script + TTS full audio。
