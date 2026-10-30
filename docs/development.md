# 開發

給要改 Berth 程式碼的人：開發環境、指令、測試、演練伺服器與實驗腳本。**本檔是開發指令的單一來源**；新增或改動指令時同輪更新這裡。使用者的部署與操作在根目錄 [README](../README.md) 與 [`docs/guide/`](guide/)。

## 環境需求

| 工具 | 版本 | 用途 |
| --- | --- | --- |
| [uv](https://docs.astral.sh/uv/) | ≥ 0.12 | 後端套件與虛擬環境管理 |
| Python | 3.13（由 `.python-version` 指定，uv 會自動下載） | 後端執行環境 |
| Node.js | ≥ 24 | 前端建置 |
| [pnpm](https://pnpm.io/) | ≥ 11 | 前端套件管理 |


## 開發指令

### 安裝

```bash
uv sync                     # 後端依賴與虛擬環境
pnpm -C web install         # 前端依賴
uv run pre-commit install   # 啟用 git hook（選用但建議；一併裝 commit-msg hook）
cp .env.example .env        # 本機的 CONFIG_ROOT
```

`.pre-commit-config.yaml` 的 `default_install_hook_types` 讓這一行同時裝 pre-commit 與 commit-msg 兩種 hook。
先前裝過的人要重跑一次，才會有 commit-msg hook。

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

`.env.example` 是完整清單；每一個都有預設值，本機開發只需要覆寫 `CONFIG_ROOT`。

| 變數 | 預設 | 用途 |
| --- | --- | --- |
| `CONFIG_ROOT` | `/config` | `berth.db`、設定與 log。啟動時自動建立並套用 migration |
| `PORT` | `8383` | 對外的唯一 port |
| `JELLYFIN_PORT` | `8096` | 套件內 Jellyfin 在宿主上發佈的 port；「在 Jellyfin 開啟」沒填對外網址時開這個 port。compose 從部署套件 `.env` 的同名變數傳進來 |
| `PROWLARR_PORT` | `9696` | 套件內 Prowlarr 在宿主上發佈的 port；精靈頁 4 與設定頁「在 Prowlarr 加私站」的連結開這個 port。compose 從部署套件 `.env` 的同名變數傳進來 |
| `QBITTORRENT_WEBUI_PORT` | `8080` | 套件內 qBittorrent 的 WebUI port（容器內外同一個號碼）；精靈頁 2 選套件內時連 `http://qbittorrent:<它>`。compose 從部署套件 `.env` 的同名變數傳進來 |
| `WEB_ROOT` | `<repo>/web/dist` | 前端 build 產物。找不到時只提供 API |
| `EXT_ROOT` | `/ext` | 其他服務唯讀掛進來的設定目錄。目前只讀 `${EXT_ROOT}/prowlarr/config.xml` 的 `<ApiKey>` |
| `PROWLARR__AUTH__APIKEY` | 無 | Prowlarr 的 API key。用這個環境變數部署 Prowlarr 的人把同一個值也給 Berth，就不必唯讀掛它的設定目錄；有值時蓋過 `config.xml` |
| `DISCORD_API_URL` | `https://discord.com/api/v10` | 通知送去的 Discord API。只有 e2e 會改：指到記下私訊的假伺服器（M4 票 133）；正式部署不要設 |
| `HOST_DATA_ROOT` | 空 | 部署 `.env` 的 `DATA_ROOT`，照寫的原樣：既有服務沒掛 `/data` 時，補法的掛載印出這個資料夾（M4 票 63）。compose 從同名的 `DATA_ROOT` 傳進來（`tests/unit/test_deploy_mounts.py` 守著兩邊是同一個值）；沒設時補法照舊印 `${DATA_ROOT}` |

**`DATA_ROOT` 不在這張表裡：Berth 不拿它找檔案。**它只在 `deploy/.env.example`，給 compose 把宿主目錄掛到容器的
`/data`（M4 票 93）；compose 另把同一個值傳成上表的 `HOST_DATA_ROOT`，只用來印在補法裡（M4 票 63）。incomplete、complete 與媒體庫的路徑來自資料庫 `settings.paths`（`PathSettings` 的預設值，
plan §9.1），不來自環境變數。

### 全部檢查

```bash
uv run pre-commit run --all-files
```

ruff、mypy、import-linter，加上 `web/` 的 prettier、eslint 與 knip。CI（`.github/workflows/ci.yml`）在 push 到
`main` 與所有 PR 上跑同一組檢查。

- **knip 擋 `web/` 沒人用的檔案、export 與依賴**（M4 票 93）：`pnpm -C web exec knip` 要 0 條。只在同一個檔裡用到的
  東西就不要 `export`——刻意不開 `ignoreExportsUsedInFile`，export 面保持最小。`web/knip.json` 只排除兩樣：
  `gen:api` 叫的外部 `uv`，與產生出來的 `schema.d.ts`；`web/gates/knip.test.ts` 對一個暫存的小專案用這份設定雙向驗它。
  Python 那一側沒有對應的閘門：vulture 的誤報率 75%–91%，不加（`docs/research/simplification-audit-2026-10-13.md`
  〈閘門建議〉）。
- **commit-msg hook 擋格式不對的 subject**：`scripts/check_commit_msg.py` 要求 Conventional Commits 的 type
  與小寫開頭，subject ≤ 72 字元；`Merge `、`Revert "`、`fixup!`、`squash!`、`amend!` 開頭的放行。
  `tests/unit/test_commit_msg.py` 雙向驗它。歷史上有幾條超長的 commit，不回溯。
- **搬文件要證明沒丟**：`uv run python scripts/docs_moved_lines.py <base-ref> <來源檔> -- <目的檔...>` 列出
  `git diff <base-ref>` 從來源檔刪掉的每一行，檢查都在目的檔裡（去頭尾空白、略過空行與表格分隔列），
  有遺失就 exit 1。封存里程碑（`docs/archive/`，見 `docs/progress.md`〈寫法與封存〉）與拆文件時用；
  `tests/unit/test_docs_moved_lines.py` 驗它。
- **CI hygiene 的 `SKIP` 跟 `language: system` 的 hook 一致**：`tests/unit/test_hygiene_skip.py` 比
  `.pre-commit-config.yaml` 裡會在 pre-commit 階段跑的 `language: system` hook 與 ci.yml hygiene 那一步的
  `SKIP`；新增這類 hook 忘了加進 `SKIP`，這裡紅（不然 CI 的 hygiene 才紅）。
- **CHANGELOG 已發版的段落不准改**：`tests/unit/test_changelog_released.py` 拿最近的 `v*` tag 上的
  `CHANGELOG.md` 對工作目錄的，tag 裡有的版本段必須原封不動；新條目寫在 `[Unreleased]`。找不到 git 或 tag
  時測試失敗而不是跳過，所以 CI 的 backend job 用 `fetch-depth: 0` 取回 tag。

## 索引

主檔之外的開發指令在 `docs/development/`，用到才讀：

| 檔案 | 內容 | 什麼時候讀 |
| --- | --- | --- |
| [`commands.md`](development/commands.md) | 〈後端〉〈帳本重建〉〈解析基準測試〉〈前端〉〈API 型別〉 | 跑單一測試、改解析器、改前端、後端改了 pydantic model |
| [`release.md`](development/release.md) | 〈發版〉 | 發版 |
| [`e2e.md`](development/e2e.md) | 〈e2e〉〈前端 e2e〉 | 跑或改真服務 e2e、前端 e2e |
| [`fake-backend.md`](development/fake-backend.md) | 〈UI 的 Fake 後端〉 | 沒有真服務時演練 UI |
| [`experiments.md`](development/experiments.md) | 〈實驗腳本〉 | 跑或新增 `scripts/experiments/` 的實驗 |

## 目錄結構

```
berth/            後端套件
  cli.py          命令列進入點（berth serve、berth openapi、berth bench、berth rebuild-ledger）
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
deploy/           部署檔（compose、.env.example，使用者只拿這兩個）與 image 的 Dockerfile
scripts/
  experiments/    對真實外部服務的驗證腳本（可重跑，結果在 docs/research/）
  fake_setup_server.py  以 Fake adapter 起一台 Berth，用來實跑驗證設定精靈
  record_tmdb_snapshots.py  錄 tests/fixtures/tmdb/ 的快照（語料加了新作品時跑）
tests/            後端測試
  e2e/              對真服務跑整條 M1 路徑（compose 覆寫檔、下載替身、pytest -m e2e）
  fixtures/e2e/     e2e 用的兩支 330 秒種子影片與冒充 RSS 站的測試 CA
  fixtures/http/    對真服務錄下來的回應，adapter 契約測試的輸入
  fixtures/mediainfo/  ffmpeg 造的一份真 Matroska（2 秒、17 KB），mediainfo adapter 的輸入
  fixtures/parser/  解析基準測試的語料（真實 torrent 的檔案清單）
  fixtures/tmdb/    語料用到的 TMDB 快照，錄一次即凍結
docs/             設計綱要、實作計劃、進度、本檔
  guide/          給使用者的英文 guide（README 連過去的那幾份）
  research/       查證與實驗的完整結果
.scratch/         各里程碑的票
```

依賴方向由 `import-linter` 強制，契約在 `pyproject.toml` 的 `[tool.importlinter]`：

- `api` 與 `pipeline` 只呼叫 `services`，不直接碰 `adapters`、`models`、`db`、`parser`、`naming`。
- `services` 可以用它下面的每一層。
- `adapters`、`models`、`parser`、`naming` 互不相依；`parser`、`naming`、`adapters` 只依賴 `domain`。
- `db` 只供 `services` 與 `models` 使用；`domain` 不依賴任何東西。

## 疑難排解

- `uv sync` 出現 `failed to hardlink ... (os error 396)`：repo 放在雲端同步目錄（OneDrive 之類）時硬鏈接不可用，改用 `UV_LINK_MODE=copy uv sync`，或在使用者層級的 `uv.toml` 設 `link-mode = "copy"`。
- 本機（目前開發用的 Windows 機器）偶發原生崩潰：退出碼 `3221225477`（0xC0000005，access violation）或
  `3221225501`（0xC000001D，illegal instruction），出現在 eslint、prettier、pytest、e2e 的 web server。同一指令
  重跑會過，與改動無關，多半是這台機器的硬體不穩（同期有多次藍屏，待送修），不是測試偶發，也不要為它開票。重跑一次仍崩才當真的失敗。
