# Jelly Weaver

PT 下载目录整理工具，为 Jellyfin 媒体库创建符合标准命名的 hardlink 结构。

## 功能概览

- 扫描 PT 下载源目录，列出待整理的媒体文件夹
- 通过 LLM（OpenAI 兼容接口）自动解析文件夹名，提取标题、年份、类型
- 用户确认/编辑解析结果后，自动创建 hardlink 到目标媒体库
- 支持 1-4 个目标库（电影/剧集），动态增删
- 实时进度推送，状态持久化
- Catppuccin Mocha 暗色主题

## 技术栈

| 层级 | 技术                               |
| ---- | ---------------------------------- |
| 后端 | Python 3.11+, FastAPI, Uvicorn     |
| 前端 | SvelteKit 5, Vite, Tailwind CSS v4 |
| 通信 | REST API + WebSocket               |
| LLM  | OpenAI 兼容 API（默认 DeepSeek）   |
| 主题 | Catppuccin Mocha                   |

## 项目结构

```
src/jelly_weaver/
├── core/           # 核心逻辑（扫描、解析、hardlink）
├── llm/            # LLM 客户端和 prompt
├── api/            # FastAPI 路由、WebSocket、依赖管理
│   └── routes/     # sources, targets, entries, settings, fs, operations
├── static/         # 前端构建产物（自动生成，不提交）
└── main.py         # 入口：启动 Uvicorn + 打开浏览器

frontend/           # Svelte 前端源码
├── src/
│   ├── components/ # UI 组件
│   ├── lib/        # API 客户端、WebSocket、状态管理、类型定义
│   └── routes/     # 页面
├── svelte.config.js
├── vite.config.ts
└── tailwind.config.ts
```

## 环境准备

### 前置要求

- Python >= 3.11
- Node.js >= 20

### 安装

```bash
# 克隆仓库
git clone <repo-url>
cd jelly-weaver

# 安装 Python 依赖
pip install -e ".[dev]"

# 安装前端依赖
cd frontend
npm install
cd ..
```

## 启动方式

### 方式一：开发模式（推荐手测时使用）

需要同时启动后端和前端开发服务器。

**终端 1 — 启动后端：**

```bash
python -m jelly_weaver.main --no-browser --port 9470
```

**终端 2 — 启动前端开发服务器：**

```bash
cd frontend
npm run dev
```

然后打开浏览器访问前端开发服务器地址（通常是 `http://localhost:5173`）。

Vite 会自动将 `/api` 请求代理到后端 `http://127.0.0.1:9470`。

### 方式二：生产模式（单服务）

先构建前端，然后只启动后端。

```bash
# 构建前端
cd frontend
npm run build
cd ..

# 启动服务
python -m jelly_weaver.main --port 9470
```

打开浏览器访问 `http://localhost:9470`。

FastAPI 会直接托管 `src/jelly_weaver/static/` 下的前端构建产物。

### 命令行参数

| 参数           | 默认值 | 说明                                 |
| -------------- | ------ | ------------------------------------ |
| `--port`       | 9470   | 服务端口                             |
| `--no-browser` | false  | 不自动打开浏览器                     |
| `--log-level`  | info   | 日志级别（debug/info/warning/error） |

## 手动测试清单

启动应用后，按以下步骤验证完整流程：

### 1. 基础启动验证

- [ ] 打开浏览器，页面正常渲染
- [ ] 顶部状态栏显示 "WebSocket connected"（绿色圆点）
- [ ] 点击 "Refresh" 按钮不报错

### 2. Settings 配置

- [ ] 点击 "Settings" 按钮
- [ ] 填入 API Base（如 `https://api.deepseek.com/v1`）
- [ ] 填入 Model（如 `deepseek-chat`）
- [ ] 填入 API Key
- [ ] 点击 "Save"
- [ ] 再次打开 Settings，确认 API Key 显示为 `sk-xxx...xxxx` 格式的遮掩值

### 3. 添加源目录

- [ ] 点击 "Add Source" 按钮
- [ ] 在目录选择器中导航到一个包含 PT 下载文件夹的目录
- [ ] 点击 "Select current" 选中该目录
- [ ] 源面板出现该目录，并列出其下的子文件夹条目
- [ ] 每个条目显示文件数量和状态（pending）

### 4. 添加目标库

- [ ] 点击右侧 "Add Library" 按钮
- [ ] 修改 Library 名称（如 "Movies"）
- [ ] 选择 Media type（movies 或 tv）
- [ ] 点击 "Browse" 选择目标目录路径
- [ ] 目标面板显示该库的现有子目录

### 5. 拖拽 → 解析 → 确认 → 链接

- [ ] 从源面板拖拽一个条目到目标库的放置区
- [ ] 等待 LLM 解析（如果已配置 API Key）
- [ ] 弹出确认对话框，显示解析结果（类型、英文标题、中文标题、年份）
- [ ] 可以手动编辑各字段
- [ ] 底部预览显示目标文件夹名：`Title (Year)`
- [ ] 点击 "Start link"
- [ ] 右下角出现进度条，显示链接进度
- [ ] 完成后，源面板中该条目状态变为 linked（绿色圆点）
- [ ] 目标库的 "Existing folders" 列表中出现新创建的文件夹

### 6. 忽略/取消忽略

- [ ] 点击某个 pending 条目右侧的 "Ignore" 按钮
- [ ] 该条目消失（因为 "Show ignored" 未勾选）
- [ ] 勾选 "Show ignored"，该条目重新出现
- [ ] 点击 "Unignore" 恢复为 pending 状态

### 7. 过滤器

- [ ] 取消勾选 "Show completed"，已链接的条目消失
- [ ] 重新勾选，已链接的条目恢复显示

### 8. 移除操作

- [ ] 点击源目录右侧的 "Remove" 按钮，该源从列表中消失
- [ ] 点击目标库的 "Remove" 按钮，该库从列表中消失

### 9. 持久化验证

- [ ] 重启服务（Ctrl+C 后重新运行）
- [ ] 刷新页面
- [ ] 之前添加的源、目标库、已链接条目状态都还在

## API 端点一览

| 方法   | 路径                         | 说明                       |
| ------ | ---------------------------- | -------------------------- |
| GET    | `/api/sources`               | 源目录列表 + 条目记录      |
| POST   | `/api/sources`               | 添加源目录                 |
| DELETE | `/api/sources`               | 移除源目录                 |
| GET    | `/api/sources/scan`          | 扫描指定源，返回条目       |
| GET    | `/api/targets`               | 目标库列表                 |
| POST   | `/api/targets`               | 新增目标库                 |
| PATCH  | `/api/targets/{id}`          | 更新目标库                 |
| DELETE | `/api/targets/{id}`          | 删除目标库                 |
| GET    | `/api/targets/{id}/contents` | 列出目标库下的子目录       |
| PATCH  | `/api/entries/{path}`        | 更新条目状态               |
| GET    | `/api/settings`              | 获取设置（不返回明文 key） |
| PUT    | `/api/settings`              | 更新设置                   |
| GET    | `/api/fs/roots`              | 平台根目录列表             |
| GET    | `/api/fs/list`               | 目录浏览                   |
| POST   | `/api/ops/parse`             | LLM 解析文件夹名           |
| POST   | `/api/ops/link`              | 发起 hardlink 任务         |

### WebSocket

连接地址：`/api/ws`

消息类型：

| type            | 说明                                                    |
| --------------- | ------------------------------------------------------- |
| `link_progress` | 链接进度（task_id, current, total）                     |
| `link_done`     | 链接完成（task_id, result）                             |
| `link_error`    | 链接失败（task_id, error）                              |
| `state_changed` | 状态变更通知（scope: sources/targets/entries/settings） |

## 状态持久化

应用状态保存在 `~/.jelly-weaver/state.json`，包括：

- 源目录列表
- 目标库配置
- 条目状态记录
- API 设置

## 文档索引

| 文件                | 说明                                   |
| ------------------- | -------------------------------------- |
| `CURRENT_STATUS.md` | 项目当前状态锚点（给开发者/AI 代理用） |
| `POC.md`            | 早期概念验证文档（部分内容已过时）     |
