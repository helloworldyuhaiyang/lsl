# LSL — Listening and Speaking Training Workspace

前端仪表盘。基于 CUE（提示/信号/线索）驱动的语言学习工作空间。

> 本项目是纯前端实现，使用模拟数据（`src/data/mockData.ts`）。后端 API 就绪后，只需替换数据获取逻辑即可对接。

---

## 技术栈

| 技术 | 版本 | 说明 |
|------|------|------|
| React | 18.x | UI 框架 |
| TypeScript | 5.x | 类型系统 |
| Vite | 7.x | 构建工具 |
| Tailwind CSS | 3.4.x | 原子化 CSS |
| shadcn/ui | — | 基于 Radix UI 的组件库 |
| React Router | 6.x | 客户端路由 |
| Lucide React | — | 图标库 |

---

## 项目结构

```
src/
├── App.tsx                 # 根组件：路由配置 + Context Provider
├── main.tsx                # 入口文件
├── index.css               # 全局样式 + Tailwind + 自定义 range input
│
├── pages/                  # 页面组件
│   ├── Dashboard.tsx       # Dashboard：统计卡片 + Session 列表
│   ├── CreateSession.tsx   # 创建 Session：Audio Upload / AI Script 双模式
│   ├── SessionDetail.tsx   # Session 详情：音频播放器 + 转录表格
│   ├── Revise.tsx          # 逐句修订：AI 改写 + TTS 设置 + 修订卡片
│   ├── Listening.tsx       # 听力练习：模拟音频播放 + 字幕同步
│   └── NotFound.tsx        # 404 页面
│
├── components/             # 业务组件
│   ├── TopNav.tsx          # 顶部导航栏（桌面 + 移动端汉堡菜单）
│   ├── SessionTable.tsx    # Session 数据表格（搜索/过滤/刷新）
│   ├── StatusBadge.tsx     # 状态徽章（completed/processing/failed/pending）
│   ├── FileUpload.tsx      # 文件拖放上传组件
│   ├── CueHighlight.tsx    # CUE 文本高亮（解析 [] 标记）
│   ├── RevisionCard.tsx    # 逐句修订卡片（textarea + 高亮叠加层）
│   ├── SubtitleCard.tsx    # 字幕卡片（点击展开/播放同步高亮）
│   ├── AudioPlayer.tsx     # 音频播放器（桌面端）
│   └── SpeakerSelect.tsx   # Speaker → TTS Voice 映射选择
│
├── components/ui/          # shadcn/ui 组件（自动生成）
│   ├── button.tsx
│   ├── input.tsx
│   ├── textarea.tsx
│   ├── select.tsx
│   ├── tabs.tsx
│   ├── table.tsx
│   ├── badge.tsx
│   ├── slider.tsx
│   ├── card.tsx
│   ├── label.tsx
│   └── skeleton.tsx
│
├── context/
│   └── AppContext.tsx      # 全局状态管理（React Context + useReducer）
│
├── hooks/                  # 自定义 Hooks
│   ├── useSessionFilter.ts # Session 搜索过滤（防抖）
│   ├── useAudioSync.ts     # 音频-字幕同步（保留，当前用 useRef 实现）
│
├── types/
│   └── index.ts            # TypeScript 类型定义
│
├── utils/                  # 工具函数
│   ├── cueParser.ts        # CUE 文本解析（提取 [] 标记）
│   ├── formatTime.ts       # 时间格式化（秒 → MM:SS）
│   └── validateForm.ts     # 表单验证
│
├── data/
│   └── mockData.ts         # 模拟数据：sessions、transcript、revision、TTS voices
│
└── lib/
    └── utils.ts            # cn() 工具函数（tailwind-merge + clsx）
```

---

## 设计系统

### 配色

| Token | 值 | 用途 |
|-------|-----|------|
| `bg-slate-50` | `#F8FAFC` | 页面背景 |
| `bg-white` | `#FFFFFF` | 卡片背景 |
| `indigo-500` | `#6366F1` | 主按钮、高亮、当前状态 |
| `slate-900` | `#0F172A` | 标题文字 |
| `slate-700` | `#334155` | 正文文字 |
| `slate-500` | `#64748B` | 次要文字 |
| `slate-400` | `#94A3B8` | 辅助文字、边框 |
| `slate-200` | `#E2E8F0` | 卡片边框 |
| `emerald-500` | `#10B981` | 完成状态 |
| `amber-500` | `#F59E0B` | 处理中状态 |
| `red-500` | `#EF4444` | 失败状态 |
| `amber-50/amber-200/amber-700` | — | CUE 高亮背景/边框/文字 |

### 字体

- **Inter**（Google Fonts），`-apple-system` 回退
- **字重**：400（正文）、500（按钮/标签）、600（标题）、700（大标题）
- **等宽字体**：用于 CUE 编辑区域（`font-mono`）

### 圆角

- `rounded-lg`（8px）：小按钮、输入框
- `rounded-xl`（12px）：卡片、大按钮
- `rounded-full`：徽章、状态标签

### 间距

- 内容最大宽度：`900px`，居中
- 页面 padding：`px-4 sm:px-6 lg:px-8`
- 卡片内边距：`p-5`（20px）
- 区块间距：`space-y-6`（24px）

---

## 状态管理

使用 **React Context + useReducer**，无需 Redux/Zustand。

```typescript
// AppContext 提供：
state: {
  sessions: Session[];        // 所有会话
  currentSession: Session | null;
  loading: boolean;
  error: string | null;
}
dispatch: (action: AppAction) => void;
getSessionById: (id: string) => Session | undefined;
```

### Action 类型

```typescript
type AppAction =
  | { type: 'SET_SESSIONS'; payload: Session[] }
  | { type: 'SET_CURRENT_SESSION'; payload: Session | null }
  | { type: 'ADD_SESSION'; payload: Session }
  | { type: 'UPDATE_SESSION'; payload: Session }
  | { type: 'DELETE_SESSION'; payload: string }
  | { type: 'UPDATE_REVISION'; payload: { sessionId: string; revision: RevisionItem[] } }
  | { type: 'SET_LOADING'; payload: boolean }
  | { type: 'SET_ERROR'; payload: string | null };
```

**当前使用模拟数据**：`mockData.ts` 中有 11 条 session 数据。对接后端时，只需在 Context 中添加 `useEffect` 调用 API，将数据通过 `dispatch({ type: 'SET_SESSIONS', payload: data })` 注入。

---

## 路由

使用 **HashRouter**，适配静态部署。

| 路由 | 页面 | 说明 |
|------|------|------|
| `/` | Dashboard | Session 管理列表 |
| `/create` | CreateSession | 创建新会话（Audio/Script 双模式） |
| `/session/:id` | SessionDetail | 查看会话详情 |
| `/session/:id/revise` | Revise | 逐句修订 |
| `/session/:id/listening` | Listening | 听力练习 |

---

## 核心组件说明

### RevisionCard — 编辑区高亮实现

使用 **双层叠加（backdrop-highlight）** 技术：

1. **Highlight div**（底层）：`pointer-events-none`，正常渲染颜色，将 `[]` 内容用琥珀色高亮
2. **Textarea**（上层）：`text-transparent`（文字透明）+ `caret-slate-800`（保留光标），负责输入
3. 两层通过 `onScroll` 同步滚动

```
┌─ Highlight Layer (z-10, pointer-events-none) ─┐
│  [热情打招呼] Hey Haiyang...          ← 琥珀色高亮 │
└──────────────────────────────────────────────┘
┌─ Textarea (z-20, text-transparent) ──────────┐
│  [热情打招呼] Hey Haiyang...          ← 透明文字，只显示光标 │
└──────────────────────────────────────────────┘
```

### Listening 页面 — 移动端优化

- **桌面端**：播放器放在内容区（正常文档流）
- **移动端**：播放器 **fixed 固定在底部**（`fixed bottom-0`），带 `backdrop-blur` + `safe-area-pb` 安全区
- **自动滚动**：当前句子始终保持在屏幕中央（`scrollIntoView({ block: 'center' })`）

---

## 响应式断点

| 断点 | Tailwind 前缀 | 调整 |
|------|--------------|------|
| < 640px | 默认 | 单列布局、移动端汉堡菜单、底部固定播放器 |
| ≥ 640px | `sm:` | 2列统计卡片、水平导航 |
| ≥ 1024px | `lg:` | 更宽的内边距 |

---

## 如何添加新功能

### 1. 添加新页面

1. 在 `src/pages/` 创建新组件（如 `Practice.tsx`）
2. 在 `src/App.tsx` 的 `Routes` 中添加路由：
   ```tsx
   <Route path="/session/:id/practice" element={<Practice />} />
   ```
3. 在相关页面的导航链接中添加入口

### 2. 添加新组件

1. 在 `src/components/` 创建组件
2. 如需使用 shadcn/ui 组件，先安装：
   ```bash
   npx shadcn add dialog          # 或其他组件
   ```
3. 使用 `cn()` 工具合并 className（已自动引入）

### 3. 添加新状态字段

1. 在 `src/types/index.ts` 的 `Session` 接口中添加字段
2. 在 `src/context/AppContext.tsx` 的 reducer 中添加处理逻辑
3. 在 `src/data/mockData.ts` 的模拟数据中补充示例值

### 4. 对接后端 API

在 `src/context/AppContext.tsx` 中添加 `useEffect`：

```typescript
useEffect(() => {
  fetch('/api/sessions')
    .then(r => r.json())
    .then(data => dispatch({ type: 'SET_SESSIONS', payload: data }));
}, []);
```

---

## 开发命令

```bash
cd /mnt/agents/output/app
npm install          # 安装依赖
npm run dev          # 开发服务器（http://localhost:5173）
npm run build        # 生产构建（输出到 dist/）
```

---

## 部署

构建产物在 `dist/` 目录，是静态 SPA，可部署到任何静态托管平台。

使用 HashRouter，所以刷新页面或 deep link 都能正常工作。
