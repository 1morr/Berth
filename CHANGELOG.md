# Changelog

本專案所有重要的變更都記在這個檔案。

格式依循 [Keep a Changelog](https://keepachangelog.com/zh-TW/1.1.0/)，版本號依循 [Semantic Versioning](https://semver.org/lang/zh-TW/)。

## [Unreleased]

### Added

- Repo 骨架：uv 後端專案與 `berth` CLI（`--version`）、pnpm + Vite + React + TypeScript 前端。
- 工具鏈：ruff、mypy（strict）、pytest、import-linter、eslint、prettier、vitest。
- `import-linter` 契約，編碼 plan §1.3 的依賴方向。
- pre-commit 設定與 GitHub Actions CI（後端 lint / type / test、前端 lint / test / build、檔案衛生）。
- LICENSE（MIT）與 README（指令的單一來源）。
- `berth serve`：FastAPI 程序，啟動時自動套用 Alembic migration 並以 WAL 開啟 `<CONFIG_ROOT>/berth.db`。
- M0 資料表：`users`、`sessions`、`settings`、`routes`、`events`（plan §2）。
- `settings` 的分組模型：`services.jellyfin`、`services.qbittorrent`、`services.indexer`、
  `services.tmdb`、`paths`、`setup`，未設定時回預設值。
- `GET /api/health`：匿名可呼叫，回總體狀態與版本。
- 前端 shell：深色為預設、亮色跟隨系統的 Tailwind 主題，`zh-Hant` 語言檔，
  TanStack Router 與 Query，以及顯示健康狀態的佔位頁；build 產物由後端同一個程序提供。
- 環境變數 `CONFIG_ROOT`、`DATA_ROOT`、`WEB_ROOT`、`PORT` 與 `.env.example`。
- `deploy/`：多階段 Dockerfile（node build → python slim、非 root、`PUID` / `PGID` 入口腳本）、
  四個服務的 `docker-compose.yml`（profiles、固定子網、健康檢查）、qBittorrent 的
  preseed 腳本與部署用的 `.env.example`。
- GHCR 發佈 workflow（`v*` tag）與 CI 的 image build job。
- `scripts/experiments/`：對真實外部服務的可重跑驗證腳本（Jellyfin 10.10 / 10.11 命名、
  qBittorrent 4.4 / 5.x 參數矩陣、Prowlarr `config/host`、硬鏈接），只用標準庫，
  可搬到 NAS 上跑；結果寫在 `docs/research/m0-experiments.md`。
- 設定精靈的前兩步（plan §9.3）：`GET /api/setup/status`、`POST /api/setup/admin`、
  `POST /api/setup/detect`、`POST /api/setup/services/{kind}`。setup 未完成時匿名開放，
  完成後需登入。
- Jellyfin、qBittorrent、Prowlarr 三個 adapter 的第一版：各有 `Protocol` 介面、HTTP 實作與
  `Fake`，錯誤分成「服務不在 compose 裡」「還在啟動」「要憑證」「不是這個服務」四種；
  契約測試對 `tests/fixtures/http/` 的錄製回應執行。
- Prowlarr 的 API key 從唯讀掛載的 `config.xml` 或 `PROWLARR__AUTH__APIKEY` 讀取，
  兩處都沒有時精靈退回手動貼上。新增環境變數 `EXT_ROOT`。
- 設定精靈 UI（`/setup`）：常駐的四格泊位板、第 1 步建立管理員、第 2 步逐服務探測與
  就地展開的既有服務連線表單與可複製的手動步驟。setup 未完成時其他頁面導向 `/setup`。
- UI 語言 `zh-Hant` 與 `en` 並列，跟隨瀏覽器並可切換，選擇存在 localStorage。
- `scripts/fake_setup_server.py`：以 Fake adapter 起一台真的 Berth，用來實跑驗證精靈。
- 設定精靈第 3 步 Jellyfin（plan §9.4、§9.5）：`GET /api/setup/jellyfin`、
  `POST /api/setup/jellyfin/bootstrap`、`/connect`、`/libraries/paths`、`/plugin`。
  套件內一鍵跑完九步（建管理員、Movies / TV / Anime 三個媒體庫、API key、安裝 MergeVersions、
  重啟並記下兩個合併任務的 `Id`），每一步冪等、失敗可單獨重試；既有服務只做檢查，
  提供「加入 Berth 路徑」與「安裝 MergeVersions」兩顆需二次確認的按鈕。
- `settings.services.jellyfin` 新增 `api_key`、`metadata_fetchers`（建立媒體庫時的 metadata
  provider，預設 TMDB，是 brief §10 的 TVDB【研究】的切換點）、`merge_movies_task_id`、
  `merge_episodes_task_id`；`settings.paths` 新增 `library_root`。
- Jellyfin adapter 補上初始精靈、媒體庫、API key、插件、排程任務；`Fake` 是有狀態的假伺服器，
  複製了實測到的行為（同名媒體庫不被拒、`Auth/Keys` 不去重、重啟後回 503）。
- `adapters/fs.py`：媒體庫目錄由 Berth 建立（plan §9.1）。

### Changed

- 依實測更正文件：brief §7.2（電影檔名必須含 `[tmdbid-<id>]` 才算多版本）、§7.7（劇集的版本
  標籤是整個檔名而非 tags）、§20.1；plan §5 的命名模板**凍結**，§8.1、§8.2、§9.2、§9.4 依
  實測修正。細節見 `docs/research/m0-experiments.md` 與 `docs/progress.md` 的「偏差與決定」。
- 視覺系統重寫成「泊位調度板」（`.impeccable/surfaces/` 的 direction contract）：四個信號色
  各只有一個意思、狀態三重編碼、無圓角無漸層。票 02 的七個佔位色彩 token 被取代。
- `settings.setup` 不再存「走到第幾步」的游標，步驟由狀態導出。
- 精靈第 2 步要**每個服務都連得上**才算做完（判定多一個 `resolved` 旗標）。原本只看「有沒有
  結論」，會讓從 `COMPOSE_PROFILES` 拿掉的服務一有結論就跳過那張唯一能填位址的表單。
- HTTP adapter 新增 `ServiceBusyError`（503）：Jellyfin 重啟後「還在載入」與「壞了」要分得開。
