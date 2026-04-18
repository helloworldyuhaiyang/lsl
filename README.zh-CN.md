# LSL

[English](README.md)

把你自己的录音，或者 AI 按需求生成的脚本，变成一套真正贴合你目标的听力素材。

## LSL 是什么

LSL 是一个以 `CUE` 为核心的听力素材生成软件。

你可以给内容加上明确的 `CUE`，例如说话场景、情绪、态度、关系、语气和节奏，让同一段内容更贴近你真正想练的听力场景。

素材来源有两种：

- 你自己的真实录音素材
- AI 根据你的需求生成的练习脚本

无论素材来自真实录音还是 AI 脚本，LSL 都会把它整理成可收听、可复盘、可继续练习的内容，而不是只给你一段一次性的文本或音频。

## 这对用户有什么价值

- 你不用再被动找现成听力素材，可以直接围绕自己要练的场景定制内容。例如你在去运营商那里办理套餐的之前可以先生成一个听力素材进行联系。
- 你自己的录音不会只停在“转写完成”这一步，AI 会对你的口语输出给出分数和者建议。可以继 revise 给出改写之后的脚本,然后生成新的听力材料。
- 如果你手里没有合适素材，可以直接让 AI 按场景、难度、轮次和关键词生成带 `CUE` 的练习脚本。
- `CUE` 直接写在句子里，控制力更细，不用把所有要求都塞进一大段抽象提示词里。

## 当前能做什么

- 上传语音文件（`mp3`、`wav`、`m4a`）并异步转写
- 手动创建文本 Session，或者根据提示词生成带 `CUE` 的 AI 对话脚本
- 对比原句和优化句，支持打分和草稿保存
- 在前端把带 `CUE` 的脚本作为单一字符串直接编辑
- 生成可直接进入 revise 流程、并为后续听力 / TTS 链路做准备的脚本数据

## 一条典型练习链路

1. 先创建一个 Session。
2. 选择素材来源：1）上传一段真实录音；2）根据要求生成脚本，例如场景、关键内容、人员角色。
3. 如果是录音，ASR 生成 transcript；如果是脚本，LLM 生成带 `CUE` 的对话内容。
4. Revision 把内容转成更适合学习和复盘的表达。
5. 同一份带 `CUE` 的脚本可以继续用于反复听和反复说的训练。

## CUE 为什么强大

在 LSL 里，脚本不是纯文本，而是“正文 + 内嵌 `CUE`”的单一可编辑字符串。

- `CUE` 统一写成 `[...]`
- `CUE` 属于脚本本身，不拆成独立字段，所以编辑、预览、合成时看到的是同一份内容
- 你可以只改 `CUE`，不改正文，就快速做出不同风格的听力版本
- 前端编辑器可以直接高亮 `CUE`，修改时更直观
- 下游 TTS 可以先提取 `CUE`，再剥离出最终朗读正文，让“怎么说”和“说什么”同时被保留下来

`CUE` 的强大之处，不是多了一个标签，而是让脚本从“只有文字”变成“文字 + 表达方式”的组合。这样生成出来的素材更接近真实对话，也更适合做模仿、跟读和听感训练。

示例：

```text
[语气平稳、就事论事地回应] Interesting, innit?
[比较随意地附和] Yeah, right.
```

## 当前实现范围

- 已完成：对象存储上传模块（Asset Module）
- 已完成：ASR 任务模块（Task Module）
- 已完成：会话管理模块（Session Module，已支持录音 / 文本类型建模）
- 已完成：Revision 模块（utterance 级 revise、打分、草稿保存）
- 已完成：AI CUE 脚本生成（生成文本 Session + synthetic transcript + completed revision）
- 已完成：模块化后端结构（`core` + `modules`）
- 已完成设计文档：TTS 模块
- 尚未完成：TTS 运行时实现、鉴权

模块设计文档：

- `backend/src/lsl/modules/asset/README.md`
- `backend/src/lsl/modules/script/README.md`
- `backend/src/lsl/modules/task/README.md`
- `backend/src/lsl/modules/session/README.md`
- `backend/src/lsl/modules/revision/README.md`
- `backend/src/lsl/modules/tts/README.md`

## TODO

- [ ] 听写模式：可以边听边默写
- [ ] 相同说话人连续多句合并成一段，降低阅读碎片感
- [ ] 用户体系：登录、身份隔离、个人练习记录
- [ ] 对接 OpenAI API

## 总体架构（Web First）

```text
[ Web Frontend ]
  - 创建 Session（录音 / 文本）
  - 文件上传
  - CUE 脚本生成与编辑（高亮输入）
  - 任务管理（上传后异步转写）
  - 转写结果展示（Diff / 编辑 / 播放）
  - 听力 / TTS 链路

        v

[ Thin Backend ]
  - 文件服务（预签名上传）
  - 任务状态管理
  - Session 管理
  - ASR / LLM / TTS 调度
  - 鉴权

        v

[ External Services ]
  - 音频存储（S3、OSS）
  - ASR / TTS 服务
  - LLM 服务
```

## 本地启动（当前后端原型）

### 1. 安装依赖

当前项目使用 `uv pip install` 安装 Python 依赖。后端原型至少需要：

```bash
uv pip install fastapi uvicorn pydantic sqlalchemy python-dotenv requests httpx openai json-repair redis alibabacloud-oss-v2
```

说明：

- `json-repair` 用于修复 revision 流程里大模型偶发返回的非严格 JSON。
- 本地开发默认已经切到 `SQLite`，不再要求先起 `PostgreSQL`。
- 如果你仍然要接 `PostgreSQL`，再额外安装 `psycopg[binary]` 和 `psycopg-pool`。
- 如果本地已经有 `uv` 管理的虚拟环境，直接在对应环境里执行即可。

### 2. 配置 `.env`

```env
# 基本配置
DATABASE_URL=sqlite:///./data/lsl.sqlite3

# 文件存储
STORAGE_PROVIDER=oss
OSS_REGION=cn-hangzhou
OSS_BUCKET=your-bucket
OSS_ACCESS_KEY_ID=your-access-key-id
OSS_ACCESS_KEY_SECRET=your-access-key-secret
ASSET_BASE_URL=https://your-bucket.oss-cn-hangzhou.aliyuncs.com

# ASR
ASR_PROVIDER=volc
VOLC_APP_KEY=your-volc-app-key
VOLC_ACCESS_KEY=your-volc-access-key
```

如果你要使用 `PostgreSQL`，把 `DATABASE_URL` 改成：

```env
DATABASE_URL=postgresql://<user>:<password>@<host>:5432/lsl
```

部署到 `PostgreSQL` 时，请先按当前最新的建表 SQL 初始化数据库。

### 3. 启动服务

```bash
uv run uvicorn --app-dir backend/src lsl.main:app --reload --env-file .env
```

## 后端目录

```text
backend/
|
|- main.py
|
|- core/
|  |- db.py
|  |- config.py
|  `- logger.py
|
`- modules/
   |- asset/
   |- task/
   |- session/
   |- revision/
   |- script/
   `- tts/
```

当前仓库实际采用 `src layout`，实际代码位于 `backend/src/lsl/`。

## 后端规范

### 分层职责

| 文件 | 职责 | 不应该做的事 |
| --- | --- | --- |
| `api.py` | FastAPI router、参数接收、HTTP 错误码转换 | 直接访问 DB、写核心业务 |
| `service.py` | 业务编排、领域规则、跨模块协作 | 写 HTTP 细节、手拼 SQL |
| `repo.py` | 持久化读写、ORM / SQL 查询、事务落库 | 做业务决策、抛 `HTTPException` |
| `model.py` | SQLAlchemy ORM / 表结构映射 | 写接口协议和业务流程 |
| `schema.py` | Pydantic 请求 / 响应模型 | 写数据库逻辑 |
| `types.py` | domain type / protocol / enum / dataclass | 依赖 FastAPI |
| `README.md` | 模块设计说明、表结构、接口约束 | 替代代码实现 |

### 依赖方向

后端必须遵守单向依赖：

`API -> Service -> Repository -> DB`

补充约束：

- `api.py` 优先返回稳定的 schema，而不是裸字典。
- `service.py` 可以依赖别的模块的 `Service`，但不能跨模块直接依赖别人的 `Repo`。
- `repo.py` 优先返回 ORM Model，不要随意返回 `dict[str, Any]`。
- `core/` 不能反向依赖 `modules/`。
- 外部厂商适配代码应放在所属模块内部。
- 能跨数据库兼容的场景，优先使用通用类型。

### 命名规范

- Router 统一命名为 `router`
- Service 类统一命名为 `XxxService`
- Repository 类统一命名为 `XxxRepository`
- ORM 类统一命名为 `XxxModel`
- Schema 命名按语义区分，例如 `CreateXxxRequest`、`UpdateXxxRequest`、`XxxData`、`XxxResponseData`

### 接口与错误处理

- `api.py` 负责把领域异常转换成 HTTP 状态码
- `service.py` 只抛业务异常，例如 `ValueError`、`RuntimeError`
- `repo.py` 负责把底层数据库异常包装成稳定的持久化错误
- 新接口默认补充输入校验、边界校验和明确的错误语义

### 配置与日志

- 所有环境变量统一从 `core/config.py` 读取
- 日志初始化统一放在 `core/logger.py`
- 业务代码获取 logger 统一使用 `logging.getLogger(__name__)`
- 日志可以记录 provider 状态、`task_id`、`session_id`，但不能输出密钥或 token

### 数据访问规范

- 简单单表 CRUD 由 `repo.py` 负责
- 查询条件、排序、分页规则必须在 repo 层显式实现
- 如果同一模块后续同时存在 ORM 和原生 SQL，也应统一收口到 `repo.py`

### 新模块准入要求

- 目录结构遵守 `api/service/repo/model/schema/README`
- 在 `README.md` 中写清楚模块职责、核心流程、外部依赖和主要数据表
- 在 `main.py` 中完成 router 注册和服务装配
