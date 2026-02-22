# LSL Frontend

LSL 前端是一个"聊天录音上传与总结"工作台，负责文件上传、任务状态展示、总结页展示。

## 技术栈

- React 19 + TypeScript 5
- Vite 7（构建与开发服务器）
- React Router 7（页面路由）
- Tailwind CSS 4（样式系统）
- shadcn/ui（基础 UI 组件）
- ESLint 9 + typescript-eslint（代码规范）

## 本地启动

在仓库根目录执行：

```bash
cd frontend
npm install
npm run dev
```

默认开发地址：`http://127.0.0.1:5173`

## 后端联调配置

前端通过 `src/lib/api/client.ts` 统一请求 API：

- 默认 `VITE_API_BASE_URL=/api`
- `vite.config.ts` 中已配置代理：`/api -> http://127.0.0.1:8000`

如果你不使用 Vite 代理，可显式设置：

```bash
VITE_API_BASE_URL=http://127.0.0.1:8000
```

## 目录结构

```text
frontend/
  src/
    app/
      layout/
        app-header.tsx
        app-shell.tsx
      providers.tsx
      router.tsx
    pages/
      upload-page.tsx
      task-page.tsx
      summary-page.tsx
      not-found-page.tsx
    components/
      common/
        page-title.tsx
        status-badge.tsx
      upload/
        file-dropzone.tsx
        upload-progress.tsx
      ui/
        button.tsx
        card.tsx
    lib/
      api/
        client.ts
        upload.ts
      constants/
        routes.ts
      storage/
        upload-history.ts
      utils/
        format.ts
      utils.ts
    mocks/
      summary.mock.ts
    types/
      api.ts
      domain.ts
    main.tsx
    index.css
```

## 路由

- `/upload`：上传页（主入口）
- `/tasks/:taskId`：任务状态页（当前为前端模拟状态流）
- `/summaries/:summaryId`：总结页（当前为 mock 总结数据 + 源音频回放）
- `/`：重定向到 `/upload`

## 组件关系与组合关系

### 全局装配关系

```text
main.tsx
└─ AppProviders
   └─ RouterProvider(router)
      └─ AppShell
         ├─ AppHeader
         └─ Outlet(当前路由页面)
```

### 页面级组合关系

`UploadPage`：

```text
UploadPage
├─ PageTitle
├─ Card (Audio Input)
│  ├─ FileDropzone
│  ├─ UploadProgress
│  └─ Button(Upload/Clear/跳转)
└─ Card (Recent Uploads)
   └─ Button(Task/Summary 跳转)
```

`TaskPage`：

```text
TaskPage
├─ PageTitle(actions: StatusBadge)
├─ Card (Pipeline Timeline)
│  └─ StatusBadge(各阶段状态)
└─ Card (Task Context)
   └─ Button(Open Summary)
```

`SummaryPage`：

```text
SummaryPage
├─ PageTitle(actions: Back Button)
├─ Card (Section Switcher)
└─ 条件渲染 Card
   ├─ Transcript Timeline
   ├─ Expression Improvements
   └─ Listening Replay(audio + URL)
```

## 上传流程（当前实现）

```text
选择文件(FileDropzone)
  -> prepareUploadUrl (/assets/upload-url)
  -> uploadToPresignedUrl (PUT upload_url)
  -> completeUploadedAsset (/assets/complete-upload)
  -> refreshRecentUploads (/assets)
  -> 写入本地 upload-history（用于 Task/Summary 串联）
```

## API 使用（当前前端）

- `POST /assets/upload-url`：申请上传 URL
- `POST /assets/complete-upload`：上传完成确认
- `GET /assets`：获取历史上传记录

说明：前端当前按 `ApiResponse<T>` 结构解析，即 `{ code, message, data }`。

## 当前状态与后续

已完成：
- 上传闭环（申请上传 URL、直传、完成确认）
- 最近上传记录展示
- 任务状态页框架
- 总结页三分区框架（mock 数据）

待完成：
- 真实任务轮询接口替换 TaskPage 模拟状态
- 真实总结接口替换 SummaryPage mock 内容
- TTS 音频与句级播放器能力
