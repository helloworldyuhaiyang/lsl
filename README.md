# LSL（Listening · Speaking · Listening）

口语录音总结软件，面向「已有口语录音」的智能复盘与学习。

## 项目目标

- 高质量口语录音复盘：转写、纠错、优化、可反复收听
- Web First：先做 Web 上传和任务流转，后续再扩展 Desktop
- 可演进架构：存储、ASR、LLM、TTS 都可替换

## 产品定位（Phase 1）

LSL 「口语录音的智能复盘工具」。

输入：
- 上传语录音文件（mp3 / wav / m4a）

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
基本配置
DATABASE_URL=postgresql://<user>:<password>@<host>:5432/lsl

文件存储
STORAGE_PROVIDER=oss
OSS_REGION=cn-hangzhou
OSS_BUCKET=your-real-bucket
OSS_ACCESS_KEY_ID=your-real-ak
OSS_ACCESS_KEY_SECRET='your-real-sk'
ASSET_BASE_URL=https://your-real-bucket.oss-cn-hangzhou.aliyuncs.com

# ASR(Automatic Speech Recognition)自动语音识别
ASR_PROVIDER='volc'
VOLC_APP_KEY='1805848308'
VOLC_ACCESS_KEY='Bxge8EJzR7jVBuqxG3G_bZGTVMlq40AQ'
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
│   |- ...
└─ tests/
```
每个功能模块相对独立，可以单独开发

说明：当前仓库实际采用 `src layout`，上面的逻辑结构在代码中对应 `backend/src/lsl/`。

### 3.1 分层职责

| 文件         | 职责                                      | 不应该做的事                       |
| ------------ | ----------------------------------------- | ---------------------------------- |
| `api.py`     | FastAPI router、参数接收、HTTP 错误码转换 | 不直接访问 DB，不写核心业务        |
| `service.py` | 业务编排、领域规则、跨模块协作            | 不写 HTTP 细节，不直接拼装 SQL     |
| `repo.py`    | 持久化读写、SQL/ORM 查询、事务落库        | 不做业务决策，不抛 `HTTPException` |
| `model.py`   | SQLAlchemy ORM / 表结构映射               | 不写接口协议和业务流程             |
| `schema.py`  | Pydantic 请求/响应模型                    | 不写数据库逻辑                     |
| `types.py`   | domain type / protocol / enum / dataclass | 不依赖 FastAPI                     |
| `README.md`  | 模块设计说明、表结构、接口约束            | 不替代代码实现                     |

### 3.2 依赖方向

后端必须遵守单向依赖：

`API -> Service -> Repository -> DB`

补充约束：

- `api.py` 返回统一使用 ApiResponse[XxxData] 返回 json 数据,其中XxxData 是Pydantic. 只能依赖当前模块的 `service.py`、`schema.py`，以及少量框架依赖。
- `service.py` 可以依赖当前模块的 `repo.py`，也可以依赖别的模块的 `Service`，但不能跨模块直接依赖别人的 `Repo`。
- `repo.py` 只依赖 `model.py`、数据库驱动、SQLAlchemy，返回ORM Model, 不要返回 dict[str, Any]。
- `core/` 不能反向依赖 `modules/`。
- 外部厂商适配代码放在所属模块内部，例如 `asset/providers.py`、`task/asr_provider.py` 与 `task/asr/*.py`，不要散落到全局。

### 3.3 模块边界

- 一个模块对外暴露的主入口是 `api.py` 和 `service.py`。

### 3.4 命名规范

- Router 统一命名为 `router`。
- Service 类统一命名为 `XxxService`。
- Repository 类统一命名为 `XxxRepository`。
- ORM 类统一命名为 `XxxModel`。
- Schema 命名按语义区分：`CreateXxxRequest`、`UpdateXxxRequest`、`XxxData`、`XxxResponseData`。

### 3.5 接口与错误处理规范

- `api.py` 负责把领域异常转换成 HTTP 状态码。
- `service.py` 只抛业务异常，例如 `ValueError`、`RuntimeError`，不直接抛 `HTTPException`。
- `repo.py` 负责把底层数据库异常包装成稳定的持久化错误，不向上暴露驱动细节。
- 所有对外接口优先返回稳定的 schema，而不是裸字典。
- 新接口默认补充输入校验、边界校验和错误语义，不允许"成功/失败全靠 message 猜"。

### 3.6 配置与日志规范

- 所有环境变量统一从 `core/config.py` 读取，不允许在业务代码里直接 `os.getenv(...)`。
- 日志初始化统一放在 `core/logger.py`。
- 业务代码获取 logger 统一使用 `logging.getLogger(__name__)`。
- 日志里可以记录 provider 状态、task_id、session_id 等追踪信息，但不能输出密钥、token、完整 AK/SK。

### 3.7 数据访问规范

- 简单单表 CRUD 由 `repo.py` 负责。
- 查询条件、排序、分页规则必须在 repo 层显式实现，不把 SQL 片段拼到 API 层。
- 如果后续同一模块同时存在 ORM 和原生 SQL，仍然要求都由 `repo.py` 统一收口。

### 3.9 新增模块准入要求

新增业务模块时，默认至少包含以下内容：

- 目录结构遵守 `api/service/repo/model/schema/README`。
- 在 `README.md` 中写清楚模块职责、核心流程、依赖外部服务、主要数据表。
- 在 `main.py` 中完成 router 注册和服务装配。
