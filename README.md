# Jelly Weaver

A PT download organizer that creates Jellyfin-compatible hardlink structures with LLM-assisted renaming.

PT 下载目录整理工具，通过 LLM 辅助重命名，为 Jellyfin 媒体库创建符合标准命名的 hardlink 结构。

---

## Features / 功能

- **Source scanning** — scan PT download directories and list folders as entries
- **LLM-powered parsing** — extract title (EN/ZH), year, and media type from folder names via OpenAI-compatible API (DeepSeek by default)
- **Merkle-based deduplication** — content hash cache prevents redundant LLM calls; rebuilding doesn't re-parse known folders
- **Drag-and-drop workflow** — drag an entry onto a target library to trigger parsing, then confirm or edit before linking
- **Hardlink creation** — creates hardlinks instead of copies; no disk space wasted
- **TV show structure detection** — auto-detects season subdirectories and flat-episode layouts
- **File group support** — multi-select individual files and link them as one entry
- **Unlink support** — remove a previously linked target folder via the UI
- **Up to 4 target libraries** — configurable movie/TV libraries with independent paths
- **Real-time progress** — WebSocket push for link progress and state changes
- **Persistent state** — sources, targets, entries, and settings survive restarts
- **Catppuccin Mocha** dark theme

---

- **扫描源目录** — 扫描 PT 下载目录，将子文件夹列为待处理条目
- **LLM 解析** — 通过 OpenAI 兼容接口（默认 DeepSeek）从文件夹名中提取标题（中/英）、年份、媒体类型
- **Merkle 去重缓存** — 基于内容哈希的缓存，避免重复调用 LLM；重新扫描时跳过已知文件夹
- **拖拽工作流** — 将条目拖到目标库触发解析，确认或编辑后执行链接
- **Hardlink 创建** — 创建硬链接而非复制，不占用额外磁盘空间
- **剧集结构检测** — 自动识别季目录和平铺剧集两种目录结构
- **文件组支持** — 多选单个文件，以一个条目的形式链接
- **取消链接** — 通过界面移除已链接的目标文件夹
- **最多 4 个目标库** — 可配置电影/剧集库，各自独立路径
- **实时进度推送** — WebSocket 推送链接进度和状态变更
- **状态持久化** — 源目录、目标库、条目状态、设置在重启后保留
- **Catppuccin Mocha** 暗色主题

---

## Tech Stack / 技术栈

| Layer / 层级 | Technology / 技术              |
| ------------ | ------------------------------ |
| Backend      | Python 3.11+, FastAPI, Uvicorn |
| Frontend     | SvelteKit 5, Vite, Tailwind CSS v4 |
| Transport    | REST API + WebSocket           |
| LLM          | OpenAI-compatible API (DeepSeek default) |
| Theme        | Catppuccin Mocha               |

---

## Project Structure / 项目结构

```
src/jelly_weaver/
├── core/           # Scanner, hardlink, Merkle tree, models
├── llm/            # LLM client and prompts
├── api/            # FastAPI routes, WebSocket, dependency injection
│   └── routes/     # sources, targets, settings, fs, operations
├── static/         # Frontend build output (auto-generated, not committed)
└── main.py         # Entry point: Uvicorn + open browser

frontend/           # SvelteKit source
├── src/
│   ├── components/ # UI components
│   ├── lib/        # API client, WebSocket, stores, types
│   └── routes/     # Pages
├── svelte.config.js
├── vite.config.ts
└── tailwind.config.ts
```

---

## Setup / 环境准备

### Prerequisites / 前置要求

- Python >= 3.11
- Node.js >= 20

### Install / 安装

```bash
# Clone the repo / 克隆仓库
git clone <repo-url>
cd jelly-weaver

# Install Python dependencies / 安装 Python 依赖
pip install -e ".[dev]"

# Install frontend dependencies / 安装前端依赖
cd frontend
npm install
cd ..
```

---

## Running / 启动方式

### Dev mode / 开发模式

Run backend and frontend separately. Vite proxies `/api` to the backend.

分别启动后端和前端，Vite 自动将 `/api` 请求代理到后端。

**Terminal 1 — Backend:**

```bash
python -m jelly_weaver.main --no-browser --port 9470
```

**Terminal 2 — Frontend dev server:**

```bash
cd frontend
npm run dev
```

Open the Vite dev server URL (usually `http://localhost:5173`).

打开浏览器访问 Vite 开发服务器地址（通常是 `http://localhost:5173`）。

### Production mode / 生产模式

Build the frontend first, then run the backend only. FastAPI serves the built assets directly.

先构建前端，后端直接托管静态文件。

```bash
cd frontend
npm run build
cd ..

python -m jelly_weaver.main --port 9470
```

Open `http://localhost:9470`.

### CLI flags / 命令行参数

| Flag           | Default | Description                             |
| -------------- | ------- | --------------------------------------- |
| `--port`       | 9470    | Server port / 服务端口                  |
| `--no-browser` | false   | Skip auto-opening browser / 不打开浏览器 |
| `--log-level`  | info    | Log level: debug/info/warning/error     |

---

## API Reference / API 端点

| Method | Path                         | Description                              |
| ------ | ---------------------------- | ---------------------------------------- |
| GET    | `/api/sources`               | List sources + entry records             |
| POST   | `/api/sources`               | Add a source directory                   |
| DELETE | `/api/sources`               | Remove a source directory                |
| GET    | `/api/sources/scan`          | Scan a source, return entries            |
| GET    | `/api/targets`               | List target libraries                    |
| POST   | `/api/targets`               | Add a target library                     |
| PATCH  | `/api/targets/{id}`          | Update a target library                  |
| DELETE | `/api/targets/{id}`          | Remove a target library                  |
| GET    | `/api/targets/{id}/contents` | List subdirectories of a target library  |
| PATCH  | `/api/entries/{path}`        | Update entry status                      |
| GET    | `/api/settings`              | Get settings (API key masked)            |
| PUT    | `/api/settings`              | Update settings                          |
| GET    | `/api/fs/roots`              | List filesystem roots                    |
| GET    | `/api/fs/list`               | Browse a directory                       |
| POST   | `/api/ops/parse`             | LLM parse a folder name                  |
| POST   | `/api/ops/link`              | Start a hardlink task                    |
| DELETE | `/api/ops/unlink`            | Remove a linked target folder            |
| POST   | `/api/ops/rename-tree`       | Get LLM rename plan for a tree           |
| DELETE | `/api/ops/name-cache`        | Clear the LLM name cache                 |

### WebSocket

Connect at: `/api/ws`

| Message type    | Payload                                                        |
| --------------- | -------------------------------------------------------------- |
| `link_progress` | `{ task_id, current, total }`                                  |
| `link_done`     | `{ task_id, result }`                                          |
| `link_error`    | `{ task_id, error }`                                           |
| `state_changed` | `{ scope: "sources" \| "targets" \| "entries" \| "settings" }` |

---

## Persistent State / 状态持久化

State is saved to `~/.jelly-weaver/state.json`, including:

状态保存在 `~/.jelly-weaver/state.json`，包括：

- Source directory list / 源目录列表
- Target library configuration / 目标库配置
- Entry status records / 条目状态记录
- LLM settings / LLM 设置
- Name cache (Merkle key → LLM suggested name) / 名称缓存
