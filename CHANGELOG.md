# Changelog

本專案所有重要的變更都記在這個檔案。

格式依循 [Keep a Changelog](https://keepachangelog.com/zh-TW/1.1.0/)，版本號依循 [Semantic Versioning](https://semver.org/lang/zh-TW/)。

## [Unreleased]

**M0（骨架）在 2026-09-08 通過驗收**（brief §17、`.scratch/m0/issues/11-m0-acceptance.md`）：在乾淨的
Windows Docker Desktop（NTFS bind mount）與 Linux（ext4）上各跑一次 `docker compose up` → 只操作 Berth
→ 四項健康檢查綠燈，全程沒有打開 qBittorrent / Jellyfin / Prowlarr 的介面；另以「既有 Jellyfin +
套件內 qBittorrent 與 Prowlarr」的組合走一次，既有媒體庫是**加**一條路徑而不是搬路徑，項目 ID 與
觀看紀錄都沒有變。M0 建的東西全部列在下面，M1 之後的變更接在同一份清單後面；還沒有發佈過正式版本。

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

- `berth openapi`：印出 OpenAPI 文件（`--output` 寫檔）。只組裝路由，不跑 lifespan、不碰資料庫。
- `pnpm -C web gen:api`：從上一條產出前端的 API 型別 `web/src/api/schema.d.ts`（openapi-typescript）。
  CI 多一個 `api-types` job，型別檔過期時紅燈。

- M1 資料表：`media`（Berth 手上的作品，資料夾名一凍結就進了檔案系統）與 `tmdb_cache`（探索與搜尋的
  一小時快取，整列丟掉不會失去任何東西）。
- TMDB adapter 補上 `trending/{tv,movie}/week`、`{tv,movie}/popular` 與 `search/multi`，以及
  **全域 40 req/s 的令牌桶**——上限是每個 IP 的，所以桶是程序層級的一個，不是每個 client 一個。
- `GET /api/discover/trending`、`/api/discover/popular`、`/api/discover/search?q=`：回作品卡片
  （tmdb id、類型、顯示用標題、英文標題、年份、完整海報網址）。**拿不到 TMDB 時仍是
  200**，理由放在 `problem`——一頁上有三個 feed，一個垮掉時另外兩個要照樣畫得出來。
- 探索頁 `/`：趨勢與熱門兩面海報牆（劇集與電影交錯）、鍵入即搜的搜尋（500 ms 防抖、2 字起跳、
  結果接管整面牆），以及 TMDB 條款要求的歸屬聲明與標誌。**卡片上還沒有狀態**——「已追蹤 /
  部分 / 完整 / 下載中」要等 Job 與帳本才推導得出來。
- `scripts/fake_setup_server.py` 新增 `discover` 與 `tmdb-down` 兩個情境；前者打**真的** TMDB
  （憑證由環境變數 `TMDB_API_KEY` 帶入，與實驗腳本同一個名字；根目錄的 `.env.example` 有欄位）。
  **Berth 本身不讀那個變數**——產品的唯一來源仍是精靈寫進資料庫的 `settings.services.tmdb.api_key`。
- TMDB adapter 再補上詳情那四支：`tv/{id}`、`movie/{id}`（各自帶它需要的 append）、
  `tv/{id}/season/{n}` 與 `tv/episode_group/{id}`。**絕對編號從 0-based 的 `order` 推**，
  不是 group 裡的 `episode_number`——後者保留播出序原值，照它讀會把第二季算成第 1 集起。
- `GET /api/media/{id}`、`POST /api/media/{id}/refresh`：TMDB 詳情與各季各集的快照
  （24 小時，過期自動重抓），以及收得下這部作品的 Route 清單。**拿不到 TMDB 時仍是 200**，
  存過的快照照樣回，只是掛一條「這是舊的」。
- Media 詳情頁 `/media/:id`：海報與三個標題（顯示用、英文、原文）、識別欄位、簡介、各季可展開的
  集表（集號、標題、絕對編號、片長、播出日），以及「入庫到哪裡」的 Route 下拉。**電影沒有季集
  區塊**，改列片長。搜尋 torrent 與送單在 M1 後段接上去之前，這一頁是唯讀的瀏覽頁。
- 探索牆的每一格現在是連到詳情頁的連結（票 03 刻意留下的那條線）。
- `domain/media.py` 的 `MediaSnapshot` / `SeasonSnapshot` / `EpisodeSnapshot`：`media.tmdb_snapshot_json`
  的型別化版本，也是 `naming` 與（M1 後段的）`parser` 的輸入。
- `naming.folder_name()`：plan §5 凍結模板的第一格——`{title} ({year}) [tmdbid-{id}]`。

### Changed

- **`/` 不再導向 `/health`**，它就是探索頁（plan §7）。登入之後落到的第一個畫面因此從「看它有沒有
  壞」變成「找東西」；健康頁留在導覽列上。
- 依實測更正 TMDB 的三件事（brief §20.3、plan §8.3）：`language` 會換掉 `trending` 回的**成員與
  順序**而不只是文字（兩輪 20 筆差 3 筆），所以清單以 `en-US` 那一輪為準、`zh-TW` 只當查表；
  回應裡的 `popularity` **不是**清單的排序依據，所以兩種作品合成一面牆時用交錯而不是重排；
  `{tv,movie}/popular` 的每一筆沒有 `media_type`。
- `settings.services.tmdb` 新增 `image_base_url`，精靈第 6 步驗憑證時順手寫下——`configuration`
  對同一把憑證是常數，每次探索都問一次是白花一個請求。
- **作品資料夾名在第一次送單成功那一刻凍結**（plan §5、brief §4.5）：那是它第一次真的通向磁碟，
  而且有人在場確認。在那之前它跟著 TMDB 的標題走，畫面上是「將會是」的預覽；凍結之後 TMDB
  改標題也不動它——已入庫的檔案不該因為別人改了條目就對不上。**「追蹤」不是一個按鈕**，它是
  「Berth 曾為這部作品下載、訂閱或入庫過」的推導結果（`CONTEXT.md`）。
- `DiscoverProblem` 更名為 `TmdbProblem` 並新增 `not_found`：探索頁與 Media 詳情頁問的是同一台
  服務、四種理由的下一步也一樣，各寫一份遲早會走樣。訊息塊因此收成共用的 `TmdbNotice`。
- TMDB 詳情的 `append_to_response` 拿掉 `external_ids` 與 `release_dates`：快照裡沒有欄位讀它們，
  而後者每部電影是一百多筆各國上映日（實測 138 筆）。plan §8.3 已同步。
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
- 前端 eslint 開啟 `@typescript-eslint/no-floating-promises` 與 `no-misused-promises`（需要型別資訊）。
  這是票 01 把型別感知規則延後時寫下的理由——TanStack Query 進來之後忘了 `await` 才變成真風險。
  只開這兩條而不是整包 `recommendedTypeChecked`：整包在這個 repo 上抓到的 36 條全是框架慣用法
  （TanStack Router 的 `throw redirect(...)`）與測試裡的型別噪音，沒有一條是真的缺陷。
- 英文的精靈階段字串從 `Berth {{code}}` 改成 `{{code}}`——`code` 本身就是 `BTH 1`，原本讀起來是 `BERTH BTH 1`。中文維持「泊位 BTH 1」：`泊位` 與 `BTH` 不同字集，而且它替第一次看到這個代號的人解釋了它是什麼。
- `routes.tsx` 的「精靈沒跑完就去跑、跑完了就要有 session」收斂成 `requireSignedInPage`
  （票 07 留的「頁面變多時再收」）。精靈那一頁仍然自己寫——它在同一個條件下是留下來而不是導走。

- 前端不再手寫任何 API 的形狀：`web/src/api/*.ts` 只把後端的類別名（`RouteOut`）換成前端在講的
  名字（`RouteView`），欄位與可選性全部來自產出的型別。M0 票 10 記的「同一份形狀寫了四層」的第四層
  就此消失。換過來的第一天就抓到一個漂移：`ServiceDetection` 少了後端已經在回的 `configured`。

- **Berth 不再內建 TMDB 的專案級憑證，改由使用者自備**（推翻上面 M0 那一條，也削掉 brief §16
  「開箱即用」的一角）。不替所有使用者背一把共用憑證；而兩個 metadata provider 在「使用者自己
  申請一把」上本來就對稱（brief §10、§20.7）。憑證的唯一來源是 `settings.services.tmdb.api_key`，
  精靈第 6 步從「可跳過的覆寫」變成**必填的閘門**：`POST /api/setup/tmdb/skip` 移除，測不過就
  停在第 6 步，`POST /api/setup/complete` 在沒有一把綠燈憑證時回 422。v3 key 與 v4 read access
  token 兩種形狀仍然都收。取得步驟寫在 README 的〈先申請一把 TMDB API key〉。
- `scripts/experiments/anime_episode_source.py` 的 TMDB 憑證改從環境變數 `TMDB_API_KEY` 讀
  （原本是從 adapter 原始碼刮那把內建的）。

### Fixed

- **英文的「{{count}} titles」在只有一筆時說「1 titles」**（探索頁的搜尋計數）。i18next 傳 `count`
  時查的是 `_one` / `_other`，兩個都沒有就退回原鍵。其他頁面既有的同類鍵尚未處理，留給 M1 的 UI 收尾。
- **一把真的 TMDB v3 API key 被當成「同形狀的假值」寫進測試**（票 08）。它從未被推送——帶著它的
  兩個 commit 都還在本地 `main` 上——但憑證仍已換掉，字串換成 `0000…0003`。假值的號碼表寫進
  `tests/fixtures/http/README.md`，那條規則現在管的不只是 fixture 檔，也管任何寫得出憑證形狀的測試。
- **泊位板的實測值標籤對比只有 3.56:1**（WCAG 2.2 AA 的驗收條件，PRODUCT.md）。`opacity-70` 疊在
  信號色塊上，正好把 `index.css` 註釋裡「白字配中明度色只有 3.6:1，過不了 AA」那個數字加了回來。
  拿掉 opacity 之後同一批標籤實測 **9.63:1**，精靈與健康頁兩塊板都適用。
- **英文版把大小寫敏感的 API 端點大寫掉**：剖面欄的 term 走 `.label`（拉丁文 `uppercase`），
  於是左欄印 `POST /LIBRARY/VIRTUALFOLDERS`、右欄印正確的 `POST /Library/VirtualFolders`，
  同一畫面兩種大小寫而其中一種不是真的端點。中文版因為 `text-transform: none` 沒有這個問題，
  所以一直沒被看到。`CutawayRow` 新增 `code` 變體給機器字串用。
- **索引站的「之後再說」按下去畫面毫無變化**：狀態存下去了，但只有 TMDB 那一節畫得出徽章。
  兩個審查代理與驗收本人都以為按鈕壞了而重複按。徽章同時改用新的 `source.deferred`
  （「之後再說」/「Deferred」）——原本借用的 `status.skipped` 是「已經是這樣」，那是冪等步驟的字。
- **`<summary>` 落回 Chrome 預設的 0.67px 焦點環**：`:focus-visible` 的選擇器漏了它。
- **「顯示」密碼按鈕 38.6 × 15px**，間距例外也不成立（距密碼框 11.5px < 12），不符 WCAG 2.2 AA 2.5.8。
- **窄版泊位板是 carousel**，BTH 3 與 BTH 4 整個在畫面外，而「一眼看出哪一格紅了」正是這塊板的
  用途；捲動容器還會變成一個沒有名字的 Tab 停留點。改回 shape brief 寫的 2×2。
- **精靈沒有出口**：設定跑完之後它就是設定入口（plan §6），但整頁沒有任何連結回得去，而設定頁
  三張服務卡片的「改位址或憑證」又全部連到裸 `/setup`（於是不管按哪一張都落在第 3 步
  「接手這台 Jellyfin」）。精靈新增 `?berth=1..4` 深連結、返回鍵，以及一句「不會重跑一次靠泊」。

- **入口腳本從來沒有接手過媒體根的擁有者**（`deploy/entrypoint.sh`）。`take_ownership` 的參數順序
  寫反，`/data` 那一次呼叫展開成 `chown /data berth:berth berth:berth`，一律失敗。Windows 上看不
  出來（那裡 `chown` 本來就會失敗且不影響寫入），但乾淨的 Linux 宿主上 Docker 新建的 `/data` 是
  `root:root`，Berth 連 `/data/library` 都建不出來，精靈第 3 步當場死。順帶讓腳本改讀
  `CONFIG_ROOT` / `DATA_ROOT`——它本來寫死路徑，與 Berth 自己讀的變數對不上。
- **qBittorrent 5.x 的登入被判成失敗**（`berth/adapters/qbittorrent/client.py`）。`auth/login` 成功時
  4.4.5 回 `200` + `Ok.`、5.2.3 回 `204` 空 body；失敗時 4.4.5 回 `200` + `Fails.`、5.2.3 回 `401`。
  原本的判定是「不是 `Ok.` 就是失敗」，所以**每一套用預設 image 的部署，qBittorrent 那一項健康檢查
  都永遠紅著**。判定改成只認 4.x 的 `Fails.`，兩個版本的實測回應都錄成 fixture。
- **Prowlarr 冷啟動時索引站清單超過探測逾時**（`berth/adapters/prowlarr/client.py`）。容器剛起來的
  第一次 `indexer/schema` 要讀進 627 份定義再組出 5.6 MB 回應，Windows 的 9p bind mount 上實測
  9.42 秒（第二次 0.34 秒），5 秒的探測逾時讓精靈第 5 步在乾淨部署上直接失敗。這一支端點改用自己的
  逾時。
