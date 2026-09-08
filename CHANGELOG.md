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
- `GET /api/health`：匿名可呼叫，回總體狀態、版本與精靈是否已完成。
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
  完成後只有 `admin` 進得來。
- Jellyfin、qBittorrent、Prowlarr 三個 adapter 的第一版：各有 `Protocol` 介面、HTTP 實作與
  `Fake`，錯誤分成「服務不在 compose 裡」「還在啟動」「要憑證」「不是這個服務」四種；
  契約測試對 `tests/fixtures/http/` 的錄製回應執行。
- Prowlarr 的 API key 從唯讀掛載的 `config.xml` 或 `PROWLARR__AUTH__APIKEY` 讀取，
  兩處都沒有時精靈退回手動貼上。新增環境變數 `EXT_ROOT`。
- 設定精靈第 7–8 步（plan §9.3）：`GET/POST /api/setup/routes` 從 Jellyfin 媒體庫建立 Library Route，
  每條 Route 在 qBittorrent 建 `berth-*` category（已存在但 save path 不同時回報衝突且不覆寫）並跑
  五項跨服務檢查——qBittorrent 與 Jellyfin 回報的路徑在 Berth 內 `stat` 得到、Jellyfin 看得到 Berth
  寫的探測檔（`Environment/ValidatePath`）、complete 目錄與寫入目標之間真的 `link()` 得起來且同
  inode。`POST /api/setup/complete` 在每條 Route 都綠燈時寫下 `settings.setup.completed`，之後
  `setup/*` 需登入、`/` 不再導向精靈。
- fs adapter（plan §8.6）：`link`、`stat`、`same_inode`、`link_test`、`free_space`、`is_within`
  與探測檔；所有寫入都要帶允許的根目錄，不在其中就拒絕（防路徑逃逸）。
- 設定精靈 UI（`/setup`）：常駐的四格泊位板、第 1 步建立管理員、第 2 步逐服務探測與
  就地展開的既有服務連線表單與可複製的手動步驟。setup 未完成時其他頁面導向 `/setup`。
- 認證（plan §6、brief §11）：`POST /api/auth/login`（以 Jellyfin 帳密驗證，角色取自
  `Policy.IsAdministrator`）、`POST /api/auth/logout`、`GET /api/auth/me`。session 以
  httpOnly、`SameSite=Strict` 的 cookie 承載，壽命 30 天不續期，資料庫只存 token 的雜湊。
- `/api` 的門禁 middleware：預設拒絕，白名單只有 `auth/login`、`auth/logout`、`health`；
  非 GET 請求要求 `X-Requested-With` 標頭。精靈跑完之後 `setup/*` 只有 `admin` 進得來。
- 登入頁 `/login`，以及登入後頁首的身分區（角色、設定入口、登出）。未登入時任何頁面
  導向 `/login`，非 admin 看不到也進不了設定。
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
- 設定精靈第 4 步 qBittorrent（plan §9.3、§8.1）：`GET /api/setup/qbittorrent/diff` 現查逐鍵差異
  （`temp_path_enabled`、`temp_path`、`save_path`、`auto_tmm_enabled`、`category_changed_tmm_enabled`），
  `POST /api/setup/qbittorrent/apply` 只寫有差異的鍵；勾了「同一組帳密」時另設套件內的 WebUI 密碼。
  Web API 低於 2.8.4 拒絕接入並給升級指令；既有服務的 temp path 未啟用只警告。
- 設定精靈第 5–6 步來源（plan §9.3、§8.3、§8.4）：`GET /api/setup/indexers`、
  `POST /api/setup/indexers/apply`（十個預設公開站，逐站顯示成敗，重按不會重複新增）、
  `/connect`（既有 Prowlarr 或任意 Torznab 端點）、`/skip`，以及 `GET /api/setup/tmdb`、
  `POST /api/setup/tmdb/test`、`/skip`。勾了「同一組帳密」時一併設定套件內 Prowlarr 的介面登入。
- qBittorrent adapter 補上偏好讀寫與分類，版本判斷（`paused` / `stopped`、2.8.4 下限）綁在
  4.4.5 與 5.2.3 兩組錄製回應上；Prowlarr adapter 補上索引站定義、新增、驗證與 `config/host`。
- 新增 TMDB 與 Torznab 兩個 adapter（各有 `Protocol`、HTTP 實作、`Fake` 與契約測試）。
  TMDB 內建專案級憑證，`settings.services.tmdb.api_key` 可覆寫，v3 key 與 v4 token 都收。
- 套件內 Prowlarr 的 API key 在探測時就存進 `settings.services.indexer`，之後的步驟與里程碑
  從同一個地方拿憑證。
- `health_checker` 背景迴圈（plan §3.2）：由 lifespan 啟動與關閉，每 30 秒醒來、上一輪滿 5 分鐘
  才真的跑，精靈跑完之前不跑。四項檢查——Jellyfin（連線與 API key）、qBittorrent（連線、Web API
  版本、建議設定漂移）、索引站（Prowlarr 或 Torznab）、每條 Route 的五項跨服務檢查（與精靈第 7 步
  同一組、寫回同一個欄位）。每一項各自 try/except，一個服務掛掉不影響其他檢查。
- `GET /api/health/detail`（要登入）與 `POST /api/health/check`（立刻重跑）：逐服務與逐 Route 的
  明細、最後成功時間、連續失敗次數與失敗原文。`GET /api/health` 的 `status` 改成由上一輪的結果
  導出（`ok` / `degraded`），只讀一列設定，不連任何服務。
- `settings` 新增 `health` 分組：迴圈上一輪的逐服務結果與 Route 總結。與 `services.*`
  分開存——那幾組是整組覆寫的使用者設定。
- 服務設定 API（plan §6，只有 `admin`）：`GET /api/settings/services`、
  `POST /api/settings/services/{kind}/test`（只重測一個服務）、`GET /api/settings/qbittorrent/diff`、
  `POST /api/settings/qbittorrent/apply`（「還原建議設定」，brief §16.3）。
- 健康頁 `/health`（唯讀，一般使用者也看得到）與服務設定頁 `/settings/services`（只有 admin）：
  與精靈同一塊四格泊位板，紅燈就地展開服務回的原文與修正步驟（套件內給 docker 指令，既有指回
  精靈），Route 綠燈收起、紅燈展開五條纜繩；qBittorrent 設定漂移顯示逐鍵差異與還原按鈕。
  頁首長出導覽，`/` 在 M1 的探索頁之前先導向 `/health`。

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
- `/api/settings/*` 只有 `admin` 進得來，規則與 `setup/*` 一樣放在門禁 middleware。
- 前端共用件從 `setup/` 移到 `components/`（纜繩、狀態對照、Route 檢查的文案與 compose 片段），
  跨頁共用的 API 型別移到 `api/schemas.ts`（後端對應 `api/schemas.py`）——精靈、健康頁與設定頁
  講的是同一批東西。
