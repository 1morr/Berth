# Berth

自託管的媒體取得與入庫協調器：把索引站或 RSS 命中的 torrent 送到 qBittorrent，下載完成後解析、比對 TMDB，以硬鏈接入庫到 Jellyfin，並維護可修復的帳本。

目前處於 M0（骨架）階段，尚不可用。設計與決定見 `docs/design-brief.md`，架構與里程碑見 `docs/plan.md`，名詞表見 `CONTEXT.md`。

## 環境需求

| 工具 | 版本 | 用途 |
| --- | --- | --- |
| [uv](https://docs.astral.sh/uv/) | ≥ 0.12 | 後端套件與虛擬環境管理 |
| Python | 3.13（由 `.python-version` 指定，uv 會自動下載） | 後端執行環境 |
| Node.js | ≥ 24 | 前端建置 |
| [pnpm](https://pnpm.io/) | ≥ 11 | 前端套件管理 |

## 開發指令

本檔是所有指令的單一來源；新增或改動指令時同輪更新這裡。

### 安裝

```bash
uv sync                     # 後端依賴與虛擬環境
pnpm -C web install         # 前端依賴
uv run pre-commit install   # 啟用 git hook（選用但建議）
cp .env.example .env        # 本機的 CONFIG_ROOT / DATA_ROOT
```

### 啟動

```bash
pnpm -C web build                                   # 前端產物（後端會提供它）
uv run --env-file .env berth serve                  # http://localhost:8383
```

開發時前後端分開跑，Vite 代理 `/api` 到後端：

```bash
uv run --env-file .env berth serve --reload         # 後端，改 .py 自動重啟
pnpm -C web dev                                     # 前端，開 Vite 印出的網址
```

### 環境變數

`.env.example` 是完整清單；四個都有預設值，本機開發只需要覆寫前兩個。

| 變數 | 預設 | 用途 |
| --- | --- | --- |
| `CONFIG_ROOT` | `/config` | `berth.db`、設定與 log。啟動時自動建立並套用 migration |
| `DATA_ROOT` | `/data` | 媒體根：incomplete、complete 與媒體庫路徑都在它底下 |
| `PORT` | `8383` | 對外的唯一 port |
| `WEB_ROOT` | `<repo>/web/dist` | 前端 build 產物。找不到時只提供 API |

### 後端

```bash
uv run berth --version      # CLI
uv run berth serve          # 啟動程序（--reload 為開發模式）
uv run pytest               # 測試
uv run ruff check .         # lint
uv run ruff format .        # 格式化（CI 用 --check）
uv run mypy                 # 型別檢查（strict）
uv run lint-imports         # 依賴方向契約（plan §1.3）
```

資料庫 migration（Alembic）。程序啟動時會自動套用到最新版本，以下只在改 schema 時用：

```bash
uv run --env-file .env alembic current                          # 目前版本
uv run --env-file .env alembic revision --autogenerate -m "…"   # 依 models/ 產生新版本
uv run --env-file .env alembic upgrade head                     # 手動套用
```

改完 `berth/models/` 一定要產生 migration：schema 不是從 models 直接建的。

### 前端

```bash
pnpm -C web dev             # Vite dev server
pnpm -C web build           # 產出 web/dist
pnpm -C web preview         # 預覽 build 產物
pnpm -C web test            # vitest（test:watch 為 watch 模式）
pnpm -C web lint            # eslint
pnpm -C web format          # prettier（CI 用 format:check）
pnpm -C web typecheck       # tsc（strict）；build 已含，這是單獨跑的快捷
```

### 全部檢查

```bash
uv run pre-commit run --all-files
```

CI（`.github/workflows/ci.yml`）在 push 到 `main` 與所有 PR 上跑同一組檢查。

## 目錄結構

```
berth/            後端套件
  cli.py          命令列進入點（berth serve）
  config.py       環境變數與路徑常數
  main.py         FastAPI app 組裝、lifespan
  adapters/       外部服務用戶端（qBittorrent、Jellyfin、TMDB…）
  api/            FastAPI routers
  db/             engine、session factory、migration 進入點
  domain/         純資料型別與狀態機
  migrations/     Alembic 環境與版本
  models/         SQLAlchemy ORM
  naming/         命名與路徑模板（純函式）
  parser/         解析階段（純函式）
  pipeline/       背景 asyncio 迴圈
  services/       改變狀態的命令函式
web/              前端（Vite + React + TypeScript）
tests/            後端測試
docs/             設計綱要、實作計劃、進度
.scratch/         各里程碑的票
```

依賴方向由 `import-linter` 強制，契約在 `pyproject.toml` 的 `[tool.importlinter]`：

- `api` 與 `pipeline` 只呼叫 `services`，不直接碰 `adapters`、`models`、`db`、`parser`、`naming`。
- `services` 可以用它下面的每一層。
- `adapters`、`models`、`parser`、`naming` 互不相依；`parser`、`naming`、`adapters` 只依賴 `domain`。
- `db` 只供 `services` 與 `models` 使用；`domain` 不依賴任何東西。

## 疑難排解

- `uv sync` 出現 `failed to hardlink ... (os error 396)`：repo 放在雲端同步目錄（OneDrive 之類）時硬鏈接不可用，改用 `UV_LINK_MODE=copy uv sync`，或在使用者層級的 `uv.toml` 設 `link-mode = "copy"`。

## 授權

MIT，見 [LICENSE](LICENSE)。
