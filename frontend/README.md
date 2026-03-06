# LSL Frontend

LSL 前端是一个口语录音学习工作台，核心流程：

`Dashboard -> Upload -> Session(Transcript) -> Revise -> Listening`

## Tech Stack

- React 19 + TypeScript 5
- Vite 7
- React Router 7
- Tailwind CSS 4
- shadcn/ui

## Local Run

```bash
cd frontend
npm install
npm run dev
```

默认地址：`http://127.0.0.1:5173`

## Routes

- `/dashboard` Dashboard：Session 管理 + 状态展示 + 搜索
- `/upload` Upload：会话信息 + 音频上传
- `/sessions/:sessionId` Session：转写主页面（Transcript）
- `/sessions/:sessionId/revise` Revise：句子优化学习
- `/sessions/:sessionId/listening` Listening：听力练习模式

兼容旧路由：

- `/tasks/:taskId` -> `/sessions/:taskId`
- `/summaries/:summaryId` -> `/sessions/:sessionId`（支持 `summary_` 前缀）

## Current Data Strategy

当前数据策略：

- Dashboard 列表：使用后端 `GET /sessions` 真实接口
- Session/Revise/Listening 页面：仍基于 `tasks(+transcript)` 兼容读取
- 上传页标题/描述仍写入浏览器 `localStorage`（等待上传流程接入 `POST /sessions`）

本地存储 key：`lsl.session-metadata.v1`

## Implemented Interaction

### Dashboard

- Session 列表（Title / Duration / Status / Created）
- Search Session（标题、描述、文件名、object_key）
- Refresh

### Upload

- Session Name（必填）
- Session Description（可选）
- Drag & Drop 上传（mp3 / wav / m4a）
- File Info：Name / Duration / Size / Format
- Upload Session 后可直接进入 Session

### Session (Transcript)

- 音频播放器（快退/快进 + 播放暂停，处理中自动轮询状态）
- 转写表格（Speaker + Time / Conversation）
- 点击句子可跳播
- `Space` 切换播放/暂停

### Revise

- 多句卡片布局（大屏多列展示）
- Suggested 文本可直接编辑
- 分数标签（绿 / 黄 / 红）直接显示句子质量，点击可展开问题详情
- `Original`（源音频切片）+ `Synthesize`（浏览器 TTS 预听）
- `Expression Cue` 提示合成语境（情绪 / 语气 / 场景）

### Listening

- Mode：Full conversation / Sentence repeat / Shadowing
- Script 区域（全文或句子列表）
- 音频控制 + 0.75x / 1x / 1.25x
- Shadowing 模式句子回放后自动跳到下一句
- `Space` 切换播放/暂停

## API Used By Frontend

- `POST /assets/upload-url`
- `POST /assets/complete-upload`
- `GET /assets`
- `POST /tasks`
- `GET /tasks`
- `GET /tasks/{task_id}`
- `GET /tasks/{task_id}/transcript`

返回体统一按：`{ code, message, data }`

## Recommended Backend Next Steps

为了彻底匹配产品语义，建议后端补充：

- `GET /sessions`（支持 query/status/page）
- `POST /sessions`（title/description）
- `GET /sessions/{session_id}`
- `GET /sessions/{session_id}/revisions`
- `GET /sessions/{session_id}/listening`
