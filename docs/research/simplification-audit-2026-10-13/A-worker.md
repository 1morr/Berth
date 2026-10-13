# A services

範圍：`berth/services/`（54 檔）。方法：vulture 兩份清單逐條 grep 判定；列出 services 全部頂層符號，數 `berth/`（不含 migrations）與 tests/scripts 的引用；人工讀相近函式。
全盤結論：沒有「整個函式或類別沒人用」的東西（`otherprod=0 且 own=0` 的符號只有 `commands.mark_of`，是測試接縫）。真正的發現集中在「同一判斷多份實作」與少數「欄位只寫不讀 / 只送不用」。

## 發現

### A1 `_utcnow()` 三份、`models.types.utcnow` 一份、再加行內 `datetime.now(UTC)`
- 類別：重複
- 是什麼：`berth/models/types.py:55` 的 `utcnow()` 已被 17 個 services 模組 import；但 `services/auth.py:234`、`services/health.py:508`、`services/setup.py:1130` 各自又定義了一模一樣的 `_utcnow()`（`return datetime.now(UTC)`）。另外 `services/discover.py:247,254`、`services/media.py:336,365` 直接寫 `datetime.now(UTC)`。
- 證據：`grep -rn "def _utcnow\|def utcnow" berth` 得 4 處；`grep -n "import.*utcnow" berth/services/*.py` 17 個檔案已在用共用版。
- 建議：保留 `models.types.utcnow`，刪三個 `_utcnow` 並改 import；行內版一併換掉。
- 大小：小
- 風險：無（內部函式）
- 值得度：高（機械式、零風險）

### A2 「在 qBittorrent 裡的狀態」集合定義了三次
- 類別：重複
- 是什麼：`{SUBMITTED, METADATA_READY, DOWNLOADING, STALLED}` 這組：`services/downloads.py:98` `IN_CLIENT_STATES`、`services/jobs.py:1017` `IN_FLIGHT`（內容完全相同，註解各自重述）；`downloads.py:86` `ACTIVE_STATES` = 這組 + `REQUESTED`；`services/plan.py:97` `ESTIMABLE` = 這組去掉 SUBMITTED，與 `downloads.py:480` 區域變數 `settled`（同樣三個狀態的 tuple）又是一份。
- 證據：`grep -rn "IN_FLIGHT\|IN_CLIENT_STATES\|ESTIMABLE\|ACTIVE_STATES" berth`：`IN_FLIGHT` 只在 `jobs.py:1031` 用一次；`IN_CLIENT_STATES` 只在 `downloads.py:126` 組 `POLLED`。tests 沒有直接引用任一個。
- 建議：只留一個 `IN_CLIENT_STATES`（放 `jobs.py` 與其他 `JobState` 集合同處，downloads 與 plan 從那 import）；刪 `IN_FLIGHT`；`ACTIVE_STATES = IN_CLIENT | {REQUESTED}`、`ESTIMABLE = IN_CLIENT - {SUBMITTED}` 由它推；`settled` 改用 `ESTIMABLE`。`inventory.UNDER_WAY_STATES`（`inventory.py:67`）也是 `ACTIVE_STATES + {COMPLETED, PLANNING, IMPORTING}`，可同法推導（可選）。
- 大小：小
- 風險：無
- 值得度：中（現在剛好一致，加新狀態時最容易漏改其中一份）

### A3 「媒體庫掛了 TVDB」判斷：`tvdb_fetchers()` 之外又手寫兩份；兩個欄位幾乎相同的 dataclass
- 類別：重複
- 是什麼：`services/jellyfin.py:136` `tvdb_fetchers(library)`（`TVDB_MARKER in fetcher.lower()`）；`jellyfin.py:1114` `_library_view` 與 `services/routes.py:1380` `_library_choice` 各自 `any(TVDB_MARKER in name.lower() for name in library.metadata_fetchers)`（輸入是 `SetupLibrary` 的扁平 `metadata_fetchers`，沒能直接呼叫前者）；`routes.py:534` 又用 `bool(tvdb_fetchers(library))`。同一段還有：`jellyfin.LibraryView`（`jellyfin.py:181`）與 `routes.LibraryChoice`（`routes.py:160`）有 `name / collection_type / locations / berth_path / has_berth_path / uses_tvdb` 六個相同欄位，兩邊都以 `berth_path(...)` + `path in library.locations` 組出來。
- 證據：`grep -rn "TVDB_MARKER" berth` 共 4 處，其中 2 處是行內重寫。
- 建議：加一支吃「fetcher 名稱序列」的 `uses_tvdb(names)`，三處都呼叫；`tvdb_fetchers` 的篩選改用它。dataclass 合併為可選第二步。
- 大小：小（判斷）／中（合併 dataclass，會動 API schema）
- 風險：只合併判斷無；合併 dataclass 會動 `/api/setup/*` 回應形狀
- 值得度：中（判斷合併）／低（dataclass 合併）

### A4 `reconcile._categories` 是 `qbittorrent.route_categories` 的逐字複本
- 類別：重複
- 是什麼：`services/reconcile.py:394-395` 與 `services/qbittorrent.py:105-107` 兩個函式內容完全相同（`{row for row in await session.scalars(select(Route.category)) if row}`）。reconcile 本來就 import `managed` / `unknown_torrents` 自 `qbittorrent`，而 `qbittorrent.managed` 的註解寫明「只有一份實作」。
- 證據：`grep -n "select(Route.category)" berth/services/*.py` 兩處；`route_categories` 被 `leftovers.py:107`、`qbittorrent.py:96` 用，`_categories` 只被 `reconcile.py:264` 用一次。
- 建議：刪 `reconcile._categories`，改 import `route_categories`。
- 大小：小
- 風險：無
- 值得度：高（註解自己宣稱「只有一份」，實際有兩份）

### A5 「Route 的 Jellyfin 媒體庫（先 id、沒有才名字）」規則三份
- 類別：重複
- 是什麼：`services/routes.py:1227` `_library_key(item_id, name)`（`item_id or name`）、`routes.py:1236` `_is_library(library, plan_row)`、`services/health_issues.py:123` `_is_library(library, route)`——同一條規則「有 `jellyfin_library_id` 就比 id，否則比 name」，後兩者函式名相同、參數型別不同（`_Planned` vs `Route`）。`health_issues.py:95` 的 docstring 還寫「`services/routes._is_library` 的同一條規則」，承認是兩份。
- 證據：`grep -rn "def _is_library" berth/services` 兩處；`inventory.py:336,346,564` 直接比 id（有 id 一定存在，不算同題）。
- 建議：在 `routes.py` 留一支 `route_library_matches(library, library_id, library_name)`，兩處呼叫；`_library_key` 同檔共用。
- 大小：小
- 風險：無
- 值得度：中（規則一變，健康檢查會跟 Route 建立流程各說各話）

### A6 `claims._route_of` 重寫了 `routes.owning_route`
- 類別：重複
- 是什麼：`services/claims.py:439-450` 對全部 Route 做 `fs.is_within` 後取最深的一條；`services/routes.py:1355-1366` `owning_route(target_path, routes)` 做同一件事（docstring：「有好幾條時是最深的那一條」），`inventory`、`review` 已在用後者。兩邊「最深」的算法還不同：claims 用 `len(Path(...).parts)`、routes 用 `len(route.target_path)`（字串長度）——在尾斜線或 `//` 的不正規路徑上可能得到不同答案。
- 證據：`grep -rn "owning_route" berth` 多處呼叫；`claims.py` 已經 `from berth.services.routes import save_path_of`，沒有 import 障礙。progress.md:884 記錄過「不正規路徑」曾造成少算。
- 建議：`_route_of` 改成 `owning_route(str(path), routes)`，找不到才 raise `UnclaimedError`；統一「最深」的衡量。
- 大小：小
- 風險：無對外介面；不正規路徑上行為可能微變，需補一個測試
- 值得度：中

### A7 TMDB 錯誤 → `TmdbProblem` 的對照寫了兩份
- 類別：重複
- 是什麼：`services/discover.py:158-173`（`_feed`）與 `services/media.py:211-229`（`read_media`）各自：`credential(settings)` 空 → `CREDENTIAL_MISSING` + `MISSING_CREDENTIAL`；`AuthFailedError` → `CREDENTIAL_REJECTED`；`ServiceError` → `UNREACHABLE`；`finally aclose`。`media.py` 多一個 `NotFoundError → NOT_FOUND`。同型的還有 `services/search.py:709` `_problem(exc)`（不同 enum `IndexerProblem`）。
- 證據：progress.md:620 記錄 `DiscoverProblem` → `TmdbProblem` 合併成共用，理由是「兩頁問的是同一台服務」；但判定那一段仍各寫一份。
- 建議：加 `tmdb_problem(exc) -> TmdbProblem`（含 NotFound），兩處 `except` 縮成一個。`search._problem` 屬另一個 enum，可不動。
- 大小：小
- 風險：無
- 值得度：低到中（目前一致，新增 TMDB 錯誤類型時要改兩處）

### A8 `with job_context(h): async with job_lock(h):` 配對重複約 10 處，`rematch.locked` 是同一件事的通用版
- 類別：重複
- 是什麼：`job_context`（`berth/logs.py:44`）+ `job_lock` 的組合在 `deletion.py:176`、`jobs.py:473,571,690,746`、`plan.py:188`、`plan_review.py:220`、`reimport.py:55`、`review.py:403` 手寫；`services/rematch.py:229` 的 `locked(*job_hashes)` 已經把「context + 排序取多把鎖」包起來（`duplicates.py:81` 用）。另有 `jobs.py:456`、`issues.py:524,602` 只拿鎖不設 `job_context`，log 就沒有 job 欄位——同一概念兩種做法。
- 證據：`grep -rn "job_context(" berth` 約 14 處；`grep -rn "job_lock(" berth/services` 約 14 處。
- 建議：把 `locked` 上移到 `jobs.py`（改名如 `job_scope`），單一 hash 也走它；缺 `job_context` 的三處是否補上要使用者決定（會改 log 內容）。
- 大小：中（動十個檔，機械替換）
- 風險：log 欄位可能增加；鎖順序語意不變。碰到鎖，每個呼叫端都要跑現有測試
- 值得度：低到中（現況沒有 bug，主要是統一 log 上下文）

### A9 `Job.last_seen_in_client_at`、`Plan.decided_at`、`JobFile.updated_at` 只寫不讀；`Plan.decided_by`、`User.last_login_at` 只有測試讀
- 類別：沒人用
- 是什麼：這幾欄在 `berth/` 只有賦值、沒有讀取，API、前端、其他 service 都沒有消費者。
  - `Job.last_seen_in_client_at`：寫在 `claims.py:234`、`downloads.py:458`；`models/job.py:71`
  - `Plan.decided_at`：寫在 `plan_review.py:162,191`、`rematch.py:604`；`models/plan.py:56`
  - `Plan.decided_by`：寫在同三處；只有 `tests/integration/test_plan_review.py:259`、`test_rematch.py:149` 斷言
  - `JobFile.updated_at`：寫在 `plan.py:561`、`reimport.py:129`；`models/job.py:96`
  - `User.last_login_at`：寫在 `auth.py:196`；只有 `tests/integration/test_auth_service.py:139` 斷言
- 證據：`grep -rnw "<欄位>" berth web/src tests`（排除 migrations）。plan.md:105/127/130/131 有列這些欄位，是計畫內的審計欄位而非遺留。先例：plan.md:130 記錄 `release_info_json`「M1 起就沒人寫」以 migration 拿掉。
- 建議：要最簡就全拿掉（含 migration 與測試斷言）；視為審計紀錄就保留。`decided_by` 的去留與 Review Queue 將來顯示「誰決定的」有關，建議使用者拍板。
- 大小：中（要 migration + 改 plan.md 資料模型一節）
- 風險：持久化資料格式 / migration（`CLAUDE.md` 要求先告知）
- 值得度：低（欄位不礙事，且有計畫文件背書；屬「使用者決定」）

### A10 API 欄位 `route_slug`（JobView）、`link_bytes` / `source_bytes`（DeletionEstimate）送出去，前端畫面沒人讀
- 類別：沒人用
- 是什麼：
  - `services/jobs.py:288`（建構在 `jobs.py:1416`）→ `api/jobs.py:188` `route_slug`。`web/src` 非測試、非 `schema.d.ts` 檔零引用。
  - `services/deletion.py:92,96`（建構在 `deletion.py:136,139`）→ `api/jobs.py:284,288`。前端只有 `JobDelete.test.tsx:16,19`、`JobDetailPage.test.tsx:112,115` 的 fixture 寫它們；畫面只讀 `reclaimable`、`links`、`sources`、`links_missing`、`sources_missing`。docstring（`deletion.py:88`、`api/jobs.py:276`）還特別說「`reclaimable` 不是 `link_bytes + source_bytes`」。後端 `tests/integration/test_deletion.py:474` 用 `estimate.source_bytes` 斷言。
- 證據：`grep -rnw "route_slug\|link_bytes\|source_bytes" web/src --include=*.ts --include=*.tsx`（排除 `schema.d.ts`）只剩測試 fixture。
- 建議：API 回應形狀可改的話，三個欄位都刪（`link_bytes`/`source_bytes` 在 service 內部若仍要算 `reclaimable` 就留成局部變數）；要當對外資訊就保留。
- 大小：小
- 風險：動到 API 回應形狀（`schema.d.ts` 重新產生、前端測試 fixture）
- 值得度：低（幾個欄位，且 `source_bytes` 有測試價值）

### A11 `PAGE_SIZE = 50` 定義兩次
- 類別：重複
- 是什麼：`services/jobs.py:100` 與 `services/inventory.py:94`；`jobs.py:99` 註解寫「與媒體庫的牆同一個數」，兩份靠註解對齊。
- 證據：`grep -n "^PAGE_SIZE" berth/services/*.py`
- 建議：確實要同一個數就讓 jobs import inventory 的；若可各自演進，改掉註解即可（那就不算重複）。
- 大小：小
- 風險：無
- 值得度：低

### 待複核疑點
- 「結束集預設起始集」規則 `episode_end or episode_start` 散在 services 8 處（`inventory.py:490`、`importer.py:431-432`、`plan.py:727,730,735`、`resolver.py:301-302`、`rss.py:1135`、`search.py:643`、`oneshot.py:149`）加 `parser/planner.py:426 episode_span`、`parser/score.py:107`。「同一集」的判準語意又不同：`importer._same_episode`（`importer.py:425`，季同且集範圍重疊）、`plan._duplicate_of`（`plan.py:715-740`，起始集相同但結束集不同 = 衝突）、`resolver.disagreement`（`resolver.py:301`，範圍相等）。三種語意本來就不同，我不認定是重複；但預設值規則可由 `LedgerEntry`／`PlanItem` 各加一個屬性或共用 `episode_span` 收攏。不確定三種語意是否真的都該不同，需使用者看過決定。
- `services/deeplink.py:49` 註解寫「與健康頁的 `_origin` 同一條規則」，但 `health.py` 沒有 `_origin`；規則（沒選就當 EXISTING）真正在 `routes.py:1308 _jellyfin_origin`，`deeplink.py:50`、`jellyfin.py:346,475` 用 `origin_of(...) is not BUNDLED` 寫等價判斷。註解過期；是否算重複看使用者，至少註解要修。
- `Recorded.issue`（`issues.py:110`）：只有測試（`test_issues.py:137,148`、`test_issues_api.py:90`）讀；產品程式碼只讀 `.opened`。是方便測試取 id 的存取，傾向保留。

## 刻意保留
- `services/jobs.py:227 held_locks`：docstring 寫明「只給測試」，是鎖字典不無限長大的唯一觀測點（`jobs.py:228-230`）；`tests/integration/test_downloads.py:781,783` 用。
- `services/events.py:61 EventHub.subscribers`：測試接縫（`tests/unit/test_events.py:43,45`、`tests/integration/test_events_api.py:135,182`）。
- `services/commands.py:53 mark_of`：`CLAUDE.md`「架構規則」段說 `tests/unit/test_command_marks.py` 守著命令標記，`mark_of` 是那個閘門的讀取端；另被 `test_setup_qbittorrent.py:149`、`test_setup_source.py:269,766,798,907` 用。
- `services/qbittorrent.py:75 managed`／`unknown_torrents`／`unknown_torrent_detail`：poller 與 reconcile 都呼叫，註解明寫「只有一份實作」（`qbittorrent.py:83-85`、`:97-99`、`:111-113`）——刻意共用（唯一破功的是 A4 的 `_categories`）。
- `services/qbittorrent.py:332 _refuse_existing` 與 `services/indexer.py:655 _refuse_existing`：形狀相同、訊息與出處（brief §16.4 紅線）不同的守衛，各服務各自一份，不併。
- `services/review.py` 內 `_count_*` / `_fetch_*` / `_*_row` 四組（audit、plan、unmatched、duplicate）：四種佇列列各有不同欄位與查詢，`ReviewRow` 聯集在 `review.py:259`；不是同一件事的兩套。
- `services/bench.py:128-136, 356-359`、`bench.py:407,443`：欄位透過 `Bucket` enum 同名（`bench.py:57,58`、註解 `bench.py:131`「以下八格與 `Bucket` 同名同義」）與 `GUARDED`／`regressions` 的字串名字動態存取，vulture 看不到。
- `models/ledger.py:54 source_inode`：帳本紀錄的一部分，`target_inode` 與它「相等就是硬鏈接成立的定義」（`models/ledger.py:57`）；目前只有寫與測試讀，但屬資料模型，不列發現。
- `services/discover.py` / `services/media.py` 各有 TTL 快取、`services/sources.py` 有記憶體 TTL：三者保存的東西與過期語意不同（`sources.py` 模組說明、`media.py:62,67` 兩種 TTL），不併。

## 工具結果判定
vulture 報的「variable／attribute」絕大多數是 frozen dataclass 欄位（經 `api/*` 序列化、前端 `schema.d.ts` 讀取）或 SQLAlchemy 欄位賦值，不是死碼。「前端讀」指 `web/src` 非測試、非 `schema.d.ts` 的實際使用檔。

### A_vulture_unused_anywhere（17 條）
| 位置 | 項目 | 判定 | 理由 |
|---|---|---|---|
| bench.py:128 | confidence_met | 誤報 | `bench.py:222` 以 kwarg 寫入、`bench.py:407,443` 以字串名字讀 |
| bench.py:134 | unmatched_correct | 誤報 | 與 `Bucket.UNMATCHED_CORRECT`（`bench.py:57`）同名，動態寫入／`_rates` 讀 |
| bench.py:135 | extra_correct | 誤報 | 同上；`bench.py:351 GUARDED` 以字串讀 |
| bench.py:136 | subtitle_correct | 誤報 | 同上 |
| bench.py:358 | Baseline.extra_correct | 誤報 | `bench.py:367` 由 `raw["extra_correct"]` 載入，`regressions` 以 `GUARDED` 字串名字存取 |
| bench.py:359 | Baseline.subtitle_correct | 誤報 | 同上 |
| deletion.py:92 | link_bytes | 真的沒人用（API 欄位，前端無消費者） | 見 A10 |
| downloads.py:458 | last_seen_in_client_at | 真的沒人讀（只寫） | 見 A9 |
| health.py:120 | interval_seconds | 誤報 | `api/schemas.py:193,206,237` 序列化，`web/src/health/PollerCard.tsx:41` 讀 |
| jobs.py:290 | user_name | 誤報 | 序列化後 `web/src/pages/JobDetailPage.tsx:99` 讀 |
| jobs.py:301 | retryable | 誤報 | 前端 `web/src/jobs/*` 14 處引用 |
| plan.py:561 | JobFile.updated_at | 真的沒人讀（只寫） | 見 A9 |
| plan_review.py:162 | Plan.decided_at | 真的沒人讀（只寫） | 見 A9 |
| plan_review.py:191 | Plan.decided_at | 真的沒人讀（只寫） | 同上（reject 路徑） |
| qbittorrent.py:158 | webapi_version | 誤報 | `web/src/setup/QbittorrentStep.tsx:161` 讀 |
| reimport.py:129 | JobFile.updated_at | 真的沒人讀（只寫） | 見 A9 |
| rss.py:193 | ever_read | 誤報 | `web/src/rss/FirstRoundSection.tsx:91` 讀 |

### A_vulture_used_only_in_tests（55 條）
| 位置 | 項目 | 判定 | 理由 |
|---|---|---|---|
| auth.py:196 | last_login_at | 只有測試讀 | 見 A9；`test_auth_service.py:139` 斷言 |
| bangumi.py:33 | bound_to | 誤報 | `web/src/media/SubscribePanel.tsx` 讀 |
| bench.py:130 | auto_correct | 誤報 | bench 動態存取（`Bucket` 同名、`GUARDED` 字串） |
| bench.py:356 | Baseline.auto_correct | 誤報 | 同上 |
| commands.py:53 | mark_of | 刻意測試接縫 | 見「刻意保留」 |
| deletion.py:90 | links_missing | 誤報 | `web/src/jobs/JobDelete.tsx` 讀 |
| deletion.py:95 | sources_missing | 誤報 | 同上 |
| deletion.py:96 | source_bytes | 真的沒人用（畫面無消費者） | 見 A10；僅 `test_deletion.py:474` 斷言 |
| events.py:61 | subscribers | 刻意測試接縫 | 見「刻意保留」 |
| first_batch.py:77 | basis | 誤報 | 前端 7 個檔讀（`JobSummary.tsx`、`firstBatchAsk.ts`、`ItemLine.tsx` 等） |
| importer.py:373 | source_inode | 只寫（ORM 欄位） | 帳本紀錄欄位，見「刻意保留」 |
| indexer.py:111 | removable | 誤報 | `web/src/setup/IndexerSites.tsx` 讀 |
| indexer.py:148 | api_key_present | 誤報 | `web/src/setup/IndexerStep.tsx` 讀 |
| indexer.py:160 | web_ui_login | 誤報 | `web/src/pages/IndexerSettingsPage.tsx` 讀 |
| indexer.py:166 | web_ui_login_by_berth | 誤報 | API 序列化，前端設定頁／精靈讀（`web_ui_login_by_berth` 2 個檔） |
| issues.py:110 | Recorded.issue | 只有測試讀 | 見「待複核」 |
| issues.py:379 | source_inode | 只寫（ORM 欄位） | 同 importer.py:373 |
| issues.py:475 | source_inode | 只寫（ORM 欄位） | 同上 |
| jellyfin.py:191 | uses_tvdb | 誤報 | `web/src/setup/RouteStep.tsx` 等讀；判斷重複見 A3 |
| jellyfin.py:194 | has_berth_path | 誤報 | `web/src/setup/RouteStep.tsx` 讀 |
| jellyfin.py:203 | api_key_present | 誤報 | `web/src/setup/JellyfinExisting.tsx`、`BerthBoard.tsx` 讀 |
| jellyfin.py:214 | bundled_default | 誤報 | `web/src/setup/autoDock.ts` 讀 |
| jobs.py:227 | held_locks | 刻意測試接縫 | 見「刻意保留」 |
| jobs.py:284 | media_title | 誤報 | `web/src/jobs/jobState.ts` 等讀 |
| jobs.py:285 | media_title_en | 誤報 | 同上 |
| jobs.py:287 | route_name | 誤報 | `web/src/jobs/JobFacts.tsx` 讀 |
| jobs.py:288 | route_slug | 真的沒人用（畫面無消費者） | 見 A10 |
| plan_review.py:161 | Plan.decided_by | 只有測試讀 | 見 A9 |
| plan_review.py:190 | Plan.decided_by | 只有測試讀 | 同上 |
| plan_view.py:62 | applied | 誤報 | `web/src/api/plans.ts`、`plans/PlanEditor.tsx` 讀 |
| qbittorrent.py:162 | blocked | 誤報 | `web/src/pages/SetupPage.tsx:857` 讀 `setup?.blocked` |
| qbittorrent.py:166 | web_ui_login | 誤報 | `QbittorrentStep.tsx`、`QbittorrentSettingsPage.tsx` 讀 |
| qbittorrent.py:173 | web_ui_login_by_berth | 誤報 | 前端讀（完成頁照它說密碼是哪一組） |
| routes.py:162 | probe_carried | 誤報 | `web/src/components/RouteCheckList.tsx` 讀 |
| routes.py:174 | has_berth_path | 誤報 | `web/src/setup/RouteStep.tsx` 讀；與 jellyfin.LibraryView 同欄見 A3 |
| routes.py:175 | uses_tvdb | 誤報 | 前端讀；判斷重複見 A3 |
| routes.py:179 | has_route | 誤報 | `web/src/setup/RouteStep.tsx:164,297` 讀 |
| routes.py:486 | route_name | 誤報 | `web/src/settings/AddRoute.tsx` 讀 |
| routes.py:499 | uses_tvdb | 誤報 | `web/src/settings/AddRoute.tsx` 讀 |
| rss.py:187 | exclusions | 誤報 | `web/src/rss/FeedSection.tsx` 等讀 |
| rss.py:221 | media_title | 誤報 | `web/src/rss/seriesByWork.ts` 讀 |
| rss.py:222 | media_title_en | 誤報 | 同上 |
| rss.py:224 | route_name | 誤報 | 同上 |
| rss.py:235 | exclusions | 誤報 | `web/src/rss/SeriesSection.tsx`、`ExclusionsSection.tsx` 讀 |
| rss.py:243 | latest_title | 誤報 | `web/src/rss/SeriesSection.tsx`、`media/SubscribePanel.tsx` 讀 |
| rss.py:244 | latest_at | 誤報 | 同上 |
| rss.py:246 | latest_episode | 誤報 | `web/src/rss/SeriesSection.tsx` 讀 |
| search.py:215 | next_seasons | 誤報 | `web/src/api/search.ts`、`media/SearchPanel.tsx` 讀 |
| setup.py:137 | waited_seconds | 誤報 | `web/src/settings/JellyfinConnection.tsx`、`setup/ServiceChoice.tsx` 讀 |
| setup.py:145 | current_step | 誤報 | `web/src/pages/SetupPage.tsx` 等讀 |
| setup.py:151 | owner_signs_in | 誤報 | `web/src/setup/OwnerStep.tsx` 讀 |
| setup.py:154 | jellyfin_startup | 誤報 | 同上 |
| setup.py:157 | window_seconds | 誤報 | `web/src/setup/signals.ts` 等讀 |
| tmdb.py:38 | api_key_present | 誤報 | `web/src/setup/TmdbStep.tsx` 讀 |
| watch.py:29 | unplayed_episodes | 誤報 | `web/src/components/watchLine.ts`、`media/WatchArea.tsx` 讀 |
