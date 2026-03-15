# Deploy

这套部署文件默认面向一台 Linux x86 服务器，使用 Docker Compose 拉起：

- `web`: 前端静态文件 + Nginx 反代
- `backend`: FastAPI
- `postgres`: PostgreSQL 16
- `redis`: Redis 7

说明：
- 应用代码默认本地开发使用 `SQLite`。
- `deploy/` 这里仍然保留 `PostgreSQL + Redis` 版本，主要用于服务器上的集中部署。

## 目录说明

```text
deploy/
├── .env.example
├── app.env.example
├── backend.Dockerfile
├── backend.requirements.txt
├── docker-compose.yml
├── initdb/
│   └── 001-schema.sql
├── nginx/
│   └── default.conf
└── web.Dockerfile
```

## 1. 复制环境变量模板

```bash
cd deploy
cp .env.example .env
cp app.env.example app.env
```

你至少要先改这几项：

- `deploy/.env`
  - `HTTP_PORT`
  - `POSTGRES_PASSWORD`
- `deploy/app.env`
  - `DATABASE_URL`
  - `STORAGE_PROVIDER`
  - `ASSET_BASE_URL`
  - `OSS_BUCKET`
  - `OSS_ACCESS_KEY_ID`
  - `OSS_ACCESS_KEY_SECRET`

如果你要接真实能力，再改：

- `ASR_PROVIDER=volc`
- `REVISION_PROVIDER=llm`
- `TTS_PROVIDER=volc`

## 2. 启动

```bash
cd deploy
docker compose up -d --build
```

查看状态：

```bash
docker compose ps
docker compose logs -f backend
docker compose logs -f web
```

## 3. 验证

健康检查：

```bash
curl http://127.0.0.1:${HTTP_PORT:-80}/health
```

页面入口：

```text
http://<your-server-ip>:<HTTP_PORT>
```

API 入口：

```text
http://<your-server-ip>:<HTTP_PORT>/api/...
```

## 4. 数据库初始化

`postgres` 容器第一次启动时，会自动执行：

- `deploy/initdb/001-schema.sql`

如果你已经有旧的 `postgres-data` volume，初始化脚本不会自动再跑。需要手动执行：

```bash
cd deploy
docker compose exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" < initdb/001-schema.sql
```

注意：
- `deploy/initdb/001-schema.sql` 现在已经统一成 `VARCHAR(32) + TEXT(JSON 字符串)`。
- 如果你之前跑过旧版 `UUID / JSONB` 表结构，推荐直接删除旧表或旧 volume 后重建，不要混用。

## 5. 常用操作

重建服务：

```bash
cd deploy
docker compose up -d --build backend web
```

停止：

```bash
cd deploy
docker compose down
```

停止并删卷：

```bash
cd deploy
docker compose down -v
```

## 6. 说明

- 前端通过同域名 `/api` 访问后端，避免额外处理 CORS。
- 后端固定单 worker，这和当前项目里 `revision` / `tts` 使用进程内线程池的实现更匹配。
- 这套文件默认在服务器上直接构建镜像。如果你在 Apple Silicon 本地构建后再推到 Linux x86 服务器，需要额外指定 `linux/amd64`。
