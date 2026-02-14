# LSL - Asset Service (Object Storage Abstraction)

Asset 是一个用于对象存储上传与访问解耦的 FastAPI 示例项目。

核心目标：
数据库只存 `object_key`，上传走 Presigned URL，访问统一用 `ASSET_BASE_URL + object_key`。

## 核心设计原则

- DB 只存 `object_key`（相对路径）
- 访问域名不入库，仅通过配置控制
- 写入使用 Presigned URL（客户端直传）
- 存储实现可插拔（`fake` / `oss`，后续可扩展 `s3` / `gcs`）
- 业务层不感知云厂商 SDK

## 架构概览

```text
Client
  |- 上传: Presigned PUT URL
  |- 访问: ASSET_BASE_URL + object_key

Backend
  |- AssetService
  |- StorageProvider (Protocol)
  |- Provider Factory
  |- FastAPI API

DB
  |- object_key
```

## 项目结构

```text
src/lsl/
|- main.py                # FastAPI 入口
|- config.py              # 配置定义
|- asset/
   |- provider.py         # StorageProvider Protocol
   |- service.py          # 业务层（key / upload_url / asset_url）
   |- factory.py          # provider 选择
   |- fake_provider.py    # 本地 fake provider
   |- oss_provider.py     # 阿里云 OSS provider
```

## 快速开始

### 1. 安装依赖（一次）

```bash
uv pip install fastapi uvicorn alibabacloud-oss-v2 python-dotenv
```

### 2. 配置 `.env`

```env
STORAGE_PROVIDER=oss
OSS_REGION=cn-hangzhou
OSS_BUCKET=your-real-bucket
OSS_ACCESS_KEY_ID=your-real-ak
OSS_ACCESS_KEY_SECRET='your-real-sk'
ASSET_BASE_URL=https://your-real-bucket.oss-cn-hangzhou.aliyuncs.com
```

说明：
- `STORAGE_PROVIDER=oss` 时，`OSS_BUCKET/OSS_ACCESS_KEY_ID/OSS_ACCESS_KEY_SECRET` 必填。
- `ASSET_BASE_URL` 用于生成读 URL，可替换为 CDN 域名。

### 3. 启动服务

```bash
uv run uvicorn --app-dir src lsl.main:app --reload --env-file .env
```

### 4. 健康检查

```bash
curl "http://127.0.0.1:8000/health"
```

## 上传接口

### `POST /assets/upload-url`

请求示例：

```bash
curl -X POST "http://127.0.0.1:8000/assets/upload-url?category=listening&entity_id=test_user&filename=log.txt&content_type=text/plain"
```

返回示例：

```json
{
  "object_key": "listening/test_user/xxxx.txt",
  "upload_url": "https://bucket.oss-cn-hangzhou.aliyuncs.com/...",
  "asset_url": "https://cdn-or-bucket-domain/listening/test_user/xxxx.txt"
}
```

## 客户端直传示例（OSS）

```bash
curl -X PUT -T /path/to/log.txt \
  -H "Content-Type: text/plain" \
  "<upload_url>"
```

注意：
- `PUT` 时 `Content-Type` 要和生成 URL 时的 `content_type` 完全一致。
- `upload_url` 必须原样使用，不要手动改 host/path/query。
- URL 默认 10 分钟过期。

## 存储切换

通过配置切换，不改业务代码：

- `STORAGE_PROVIDER=fake`
- `STORAGE_PROVIDER=oss`

`asset_url` 始终由 `ASSET_BASE_URL + object_key` 生成。

## 常见问题

### 1) `ModuleNotFoundError: No module named 'dotenv'`

原因：使用了 `--env-file`，但没安装 `python-dotenv`。

处理：

```bash
uv pip install python-dotenv
```

### 2) `Bucket name is invalid`

原因：`OSS_BUCKET` 为空或未加载 `.env`。

处理：检查 `.env`，并确认启动命令包含 `--env-file .env`。

### 3) `SignatureDoesNotMatch`

常见原因：
- `PUT` 请求头 `Content-Type` 与签名时不一致
- 手动修改了 `upload_url`
- `OSS_REGION`、AK/SK 与 bucket 不匹配
- 上传时 URL 已过期

## 后续扩展

- S3 / MinIO / R2 provider
- GCS provider
- CDN 私有回源
- 上传策略校验（类型/大小/key 前缀）
- 单元测试与集成测试
