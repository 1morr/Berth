# Berth

自託管的媒體取得與入庫協調器：把索引站或 RSS 命中的 torrent 送到 qBittorrent，下載完成後解析、比對 TMDB，以硬鏈接入庫到 Jellyfin，並維護可修復的帳本。

目前處於 M0（骨架）階段，尚不可用。設計與決定見 `docs/design-brief.md`，架構與里程碑見 `docs/plan.md`，名詞表見 `CONTEXT.md`。

## 部署

`deploy/` 是完整的 compose 套件：Berth 加 qBittorrent、Jellyfin、Prowlarr，四個容器掛同一個媒體根。Linux 與 Windows 共用同一份 `docker-compose.yml`。

```bash
cd deploy
cp .env.example .env        # 改 DATA_ROOT 與 CONFIG_ROOT
docker compose up -d
```

開 <http://localhost:8383>，之後所有設定都在 Berth 的精靈裡完成，不需要分別打開另外三個服務的介面。

> M0 階段 GHCR 上還沒有發佈過 image（第一個 `v*` tag 之前都沒有），現在要跑 compose 得先在 repo 根目錄自己 build 一份：見下面的〈自己 build image〉。

| 服務 | Port | 備註 |
| --- | --- | --- |
| Berth | 8383 | 唯一需要開的介面 |
| qBittorrent | 8080（WebUI）、6881（BT） | WebUI 要密碼，密碼在精靈裡設定 |
| Jellyfin | 8096 | |
| Prowlarr | 9696 | |

已經有其中某個服務的人，把它從 `.env` 的 `COMPOSE_PROFILES` 拿掉，精靈會改用「既有服務」的表單接入；`berth` 沒有 profile，永遠會啟動。變數清單見 `deploy/.env.example`，裡面沒有任何秘密欄位。

### 硬鏈接前提

入庫是硬鏈接不是複製，所以：

- **只掛一個媒體根**：下載目錄與媒體庫都要在 `DATA_ROOT` 底下。分成兩個 bind mount 會得到 `EXDEV`，建立 Route 時的檢查會直接擋下來。
- **檔案系統要支援硬鏈接**：exFAT 不行；btrfs 子卷、ZFS dataset、mergerfs branch 之間也不行，它們在核心眼中是不同的裝置。
- **同一台機器**：Berth 與 qBittorrent 要看得到同一份檔案，跨主機與 remote path mapping 不支援。

### 支援的宿主平台

- **Linux**（NAS 與伺服器）：`DATA_ROOT` 要能被 `PUID` / `PGID` 寫入，例如 `chown -R 1000:1000 /srv/berth/data`。Berth 只在媒體根還是空目錄時自動接手擁有者；已經有內容的目錄一律不碰。
- **Windows**（Docker Desktop、WSL2 後端）：用一般的 bind mount 就好（`DATA_ROOT=C:\Berth\data`），不需要 named volume，NTFS 上的硬鏈接實測可用（brief §20.7）。`PUID` / `PGID` 在這種掛載上沒有意義，維持預設即可。

### 外部服務的前提

- **qBittorrent**：最低 4.4（Web API 2.8.4）。套件內的容器由 `deploy/preseed/qbittorrent/10-berth.sh` 在服務啟動前補上免密白名單，而且只放行 Berth 那一個固定 IP —— 4.6.1 起首次啟動的隨機密碼只印在容器 log，沒有這一步 Berth 進不去；WebUI 從宿主或 LAN 進來仍然要密碼。其餘偏好（temp path、save path、category 的 autoTMM）與 WebUI 密碼由精靈經 API 設定，按之前會顯示差異。腳本不覆蓋任何已經有值的設定。
- **Jellyfin**：同一部片的多個版本要合併需要 [MergeVersions](https://github.com/danieladov/jellyfin-plugin-mergeversions) 插件。套件內的 Jellyfin 由精靈自動安裝並重啟；既有的 Jellyfin 是一顆要確認的按鈕。
- **Prowlarr**：不預置任何東西，Berth 唯讀掛載它的設定目錄以讀取它自動產生的 API key。

### 秘密與備份

各服務的 API key 與密碼存在 `${CONFIG_ROOT}/berth/berth.db`，靠檔案權限保護，不做應用層加密（與 Seerr 相同）。備份 Berth 就是複製 `${CONFIG_ROOT}/berth`。

### 自己 build image

```bash
docker build -f deploy/Dockerfile -t ghcr.io/1morr/berth:latest .
```

發佈由 `.github/workflows/release.yml` 在 `v*` tag 上推到 GHCR。

### 部署疑難排解

image 裡沒有 curl。要從 Berth 這一端測外部服務時：

```bash
docker compose exec berth python -c \
  "import urllib.request; print(urllib.request.urlopen('http://qbittorrent:8080/api/v2/app/version').read())"
```

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
deploy/           部署套件：Dockerfile、compose、preseed、.env.example
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

## 授權與歸屬

MIT，見 [LICENSE](LICENSE)。

<img src="docs/assets/tmdb.svg" alt="TMDB" height="28">

This product uses the TMDB API but is not endorsed or certified by TMDB.
（本產品使用 TMDB 的 API，但未經 TMDB 認可或認證。TMDB 的條款限非商業使用。）
