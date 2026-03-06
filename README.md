# LSL（Listening · Speaking · Listening）

口语录音总结软件，面向「已有口语录音」的智能复盘与学习。

## 项目目标

- 高质量口语录音复盘：转写、纠错、优化、可反复收听
- Web First：先做 Web 上传和任务流转，后续再扩展 Desktop
- 可演进架构：存储、ASR、LLM、TTS 都可替换

## 产品定位（Phase 1）

LSL 「口语录音的智能复盘工具」。

输入：
- 已有口语录音文件（mp3 / wav / m4a）

输出：
- 可读的文本(转写的)
- 可学习的表达对比（原句 vs 优化句）
- 用户可编辑的对话脚本
- 可反复收听的听力材料（TTS）

## 总体架构（Web First）

```text
[ Web Frontend ]
  - 文件上传
  - 任务管理（上传后异步转写）
  - 转写结果展示（Diff / 编辑 / 播放）

        ↓

[ Thin Backend ]
  - 文件服务（Asset moudle, 前端使用生成好的预签名 url , put 文件到云端）
  - 任务状态管理(Task module)
  - 聊天管理(Session module)
  - ASR / LLM / TTS 调度
  - 鉴权

        ↓

[ External Services ]
  - 音频存储(S3, OSS)
  - ASR / TTS
  - LLM 服务
```

## 功能设计

### Web Frontend

- 音频文件上传：单文件代表一个口语录音，上传前显示时长与大小
- 上传与任务触发：前端拿 PUT URL 直传 OSS，后端创建异步任务
- 任务状态页：`uploaded` → `transcribing` → `analyzing` → `completed/failed`
- 转写结果展示：按时间顺序展示，支持老师/学员区分与片段回放
- 表达纠错与优化：句子级输出原句、问题点、优化句
- Diff 学习视图：高亮新增/删除并展示修改原因
- 听力材料生成：TTS 生成可反复收听音频并缓存

### Thin Backend

- STS/签名服务：隐藏云厂商凭证，提供上传授权能力
- ASR 调度：提交转写、管理异步任务、存储结果
- 任务管理：记录音频地址、文件 hash、处理状态，避免重复提交
- 文本结构化：句子切分、角色区分、保留时间戳
- LLM 分析：输出结构化纠错与优化结果
- Diff 数据生成：后端产出统一 diff 数据结构，前端只渲染
- TTS 调度：控制频率和成本，预留音色扩展

## 当前实现范围（截至目前）

- 已完成：对象存储上传模块（Asset Module）
- 已完成：ASR 任务模块（Task Module）
- 已完成：会话管理模块（Session Module）
- 已完成：模块化后端结构（`core` + `modules`）
- 未完成：LLM/TTS 调度、鉴权、前端页面

模块详细文档见：
- `backend/src/lsl/modules/asset/README.md`
- `backend/src/lsl/modules/task/README.md`
- `backend/src/lsl/modules/session/README.md`

## 本地启动（当前后端原型）

1. 配置 `.env`

```env
STORAGE_PROVIDER=oss
OSS_REGION=cn-hangzhou
OSS_BUCKET=your-real-bucket
OSS_ACCESS_KEY_ID=your-real-ak
OSS_ACCESS_KEY_SECRET='your-real-sk'
ASSET_BASE_URL=https://your-real-bucket.oss-cn-hangzhou.aliyuncs.com
DATABASE_URL=postgresql://<user>:<password>@<host>:5432/lsl
```

2. 启动服务

```bash
uv run uvicorn --app-dir backend/src lsl.main:app --reload --env-file .env
```

3. 后端规范
```
backend/
│
├─ main.py
│
├─ core/
│   ├─ db.py
│   ├─ config.py
│   └─ logger.py
│
├─ modules/
│
│   ├─ asset/
│   │   ├─ api.py
│   │   ├─ service.py
│   │   ├─ repo.py
│   │   ├─ model.py
│   │   ├─ schema.py
│   │   ├─ types.py
│   │   └─ README.md
│   │
│   ├─ task/
│   │   ├─ api.py
│   │   ├─ service.py
│   │   ├─ repo.py
│   │   ├─ model.py
│   │   ├─ schema.py
│   │   └─ README.md
│   │
│   ├─ session/
│   │   ├─ api.py
│   │   ├─ service.py
│   │   ├─ repo.py
│   │   ├─ model.py
│   │   ├─ schema.py
│   │   └─ README.md
│
└─ tests/
```
每个功能模块相对独立，可以单独开发