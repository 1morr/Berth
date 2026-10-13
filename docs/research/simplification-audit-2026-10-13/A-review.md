# A 複核

複核方式：每條都重新 grep `berth/`、`tests/`、`scripts/`、`web/src`（排除 `migrations/`、`schema.d.ts`、`__pycache__`），打開兩邊程式碼對讀；保留理由查 `docs/progress.md` 與程式註解。另以腳本重跑「services 頂層符號在定義檔外零引用」：結果只有 `commands.mark_of`（tests 3 檔），與 worker 的全盤結論一致。

| 編號 | 判定 | 理由（附自己查到的證據） | 修正後的建議 / 大小 / 風險（若有改） |
|---|---|---|---|
| A1 | 通過 | `grep "def _utcnow\|def utcnow" berth`：`models/types.py:55` 加 `auth.py:234`、`health.py:508`、`setup.py:1130`，四份都是 `return datetime.now(UTC)`。行內版：`discover.py:247,254`、`media.py:336,365`。tests 與 scripts 沒有人引用或 monkeypatch `_utcnow`（tests 只 import `models.types.utcnow`），所以它不是測試接縫。services → models 的依賴方向合法。progress.md 沒有保留理由。 | 不變。註：`pipeline/*`、`adapters/budget.py` 的 `lambda: datetime.now(UTC)` 是注入時鐘的預設值，不在 A 的範圍；`pipeline/reconciling.py:43` 用本地時間，語意不同，不要一起換。 |
| A2 | 通過但修正 | `IN_FLIGHT`（`jobs.py:1017`）與 `IN_CLIENT_STATES`（`downloads.py:98`）集合相同，都在說「已交給 qBittorrent、還沒完成」這段狀態。新增一個客戶端內的前置狀態時兩份都要改，這是真重複。tests 沒有引用任一個（已 grep）。不過 `ESTIMABLE`（`plan.py:97`，「清單到手、還在下載」，brief §5.1）、`ACTIVE_STATES`（`downloads.py:86`，決定輪詢間隔，刻意含 `REQUESTED`）、`settled`（`downloads.py:480`，「可能走到 completed」）和 `UNDER_WAY_STATES` 回答的是不同問題，只是目前剛好可以由同一組推出來。硬要互相推導是寫法偏好，不屬於「兩套做法」。 | 只收 `IN_FLIGHT` 對 `IN_CLIENT_STATES` 這一對：保留一份放在 `jobs.py`（downloads 已經 import jobs，jobs 沒有 import downloads，不會循環），刪 `IN_FLIGHT`。`ESTIMABLE`、`ACTIVE_STATES`、`settled`、`UNDER_WAY_STATES` 由它推導的部分降為可選，不列發現。大小：小；風險：無。 |
| A3 | 通過但修正 | 判斷重複成立：`jellyfin.py:1114` 與 `routes.py:1380` 都行內寫 `any(TVDB_MARKER in name.lower() for name in library.metadata_fetchers)`，和 `tvdb_fetchers`（`jellyfin.py:134`）用同一個述詞，只是輸入型別不同（`SetupLibrary.metadata_fetchers` 是攤平後的清單，見 `models/setting.py:248`）。`tvdb_fetchers` 的 docstring 自己寫「Route 設定頁與 health_checker 問的是同一件事」。dataclass 合併不成立：`LibraryChoice`（`routes.py:166`）多了 `supported`、`has_route`、`target_path`、`listed`，`LibraryView`（`jellyfin.py:185`）多了 `metadata_fetchers`。兩者是精靈兩個不同步驟的回應形狀，重疊的六個欄位是同一份來源的投影，不是同一概念的兩份實作。 | 只做判斷合併：加 `uses_tvdb(names: Iterable[str]) -> bool`（同步函式，不受 `@command` 規則管），三處都改呼叫它。dataclass 合併從建議中拿掉（駁回）。大小：小；風險：無。 |
| A4 | 通過 | `reconcile.py:394-395` 與 `qbittorrent.py:105-107` 逐字相同。`_categories` 只有 `reconcile.py:264` 一處呼叫。reconcile 已經 `from berth.services.qbittorrent import (...)`（`reconcile.py:73`），沒有 import 障礙。`managed` 的 docstring（`qbittorrent.py:83-85`）寫「只有一份實作」。 | 不變。 |
| A5 | 通過 | `routes._is_library`（`routes.py:1236`，吃 `_Planned`）、`health_issues._is_library`（`health_issues.py:123`，吃 `Route`）規則相同：有 id 比 id，否則比名字。`routes._library_key`（`routes.py:1227`）是同一規則的 key 版本。`health_issues.py:95` 的 docstring 引用了 routes 那一份。health_issues 目前 import clients、issues、jellyfin、settings；routes 與它的依賴都不 import health_issues，所以由 health_issues 改 import routes 不會循環，也不違反 import-linter（同屬 services 層）。 | 不變。新函式是同步函式，不受 `test_command_marks` 規則管。 |
| A6 | 通過但修正 | `claims._route_of`（`claims.py:440`）與 `routes.owning_route`（`routes.py:1357`）都是「全部 Route 做 `is_within`，取最深的」。差別：claims 用 `len(Path(...).parts)`，routes 用 `len(route.target_path)`。Route 的 `target_path` 存檔時不正規化：progress.md 2026-09-15 票 14a 有 `…/tv//anime` 這種 Route，測試也這樣釘住。所以字串長度在 `/data/library/tv////` 對上 `/data/library/tv/anime` 這種情況會選錯；**有潛在 bug 的是 `owning_route`，claims 那一份反而對**。 | 統一方向要寫清楚：`owning_route` 改用 `len(Path(route.target_path).parts)`（或比正規化後的長度），`_route_of` 改呼叫它，找不到就 raise `UnclaimedError`。風險修正：會改到 `inventory`、`resolver`、`routes._usage_of` 等既有呼叫端在不正規路徑上的歸屬（多數是修正），要補一個「不正規但較淺的 Route 對上較深的 Route」的測試。大小：小。 |
| A7 | 通過但修正 | `discover.py:158-171` 與 `media.py:211-229` 對 TMDB 錯誤的對照相同，`TmdbProblem` 的 docstring（`domain/enums.py:34-35`）明說合成一個 enum 就是怕兩份走樣。但 `NotFoundError` 是 `ServiceError` 的子類（`adapters/http.py:73`）：discover 目前把 404 對到 `UNREACHABLE`，web/src 的探索頁也沒處理 `not_found`。共用函式如果照 worker 的建議含 NotFound，discover 的行為會變。 | `tmdb_problem(exc)` 只對三種共同錯誤（缺憑證、`AuthFailedError`、`ServiceError`），`media.py` 的 `NotFoundError` 分支留在自己那裡，放在共用呼叫之前。要不要把 NotFound 一併收進來由使用者決定，因為會改探索頁的行為。大小：小；風險：照修正後的做法沒有。 |
| A8 | 駁回 | `job_context` 與 `job_lock` 是兩個可以組合的原語，單筆的呼叫端把兩者疊在一起，並沒有另外實作一份 `rematch.locked`。`locked` 是多筆、排序取鎖的版本，這屬於寫法偏好，不是「兩套做法」。證據也有錯：worker 說 `jobs.py:456` 只拿鎖沒設 `job_context`，但它在 `jobs.py:404` 的 `with job_context(torrent.info_hash):` 區塊裡（404–457 之間沒有頂層行）。只有 `issues.py:524`（`_replan`）與 `issues.py:602`（`_restart`）真的沒有 job_context，它們的呼叫端 `resolve_issue`（`issues.py:227`）也沒設。這是 log 可觀測性的缺口，不屬於本票的兩類。 | 不列發現。`issues._replan`、`_restart` 缺 job_context 可以另記為觀測性問題，交使用者決定。 |
| A9 | 通過 | 重新 grep（排除 migrations）：`last_seen_in_client_at` 只在 `claims.py:234`、`downloads.py:458` 寫入；`decided_at` 只在 `plan_review.py:162,191`、`rematch.py:604` 寫入；`decided_by` 寫在同三處，讀取只有 `test_plan_review.py:259`、`test_rematch.py:149`；`JobFile.updated_at` 只在 `plan.py:561`、`reimport.py:129` 寫入；`last_login_at` 只在 `auth.py:196` 寫入，讀取只有 `test_auth_service.py:139`。`berth/` 裡沒有泛用的 ORM 欄位序列化（沒有 `__table__.columns` 這類寫法），web/src 零引用。plan.md:105、127、131 把這些欄位列進資料模型。 | 不變。只寫不讀的 `LedgerEntry.source_inode` 應該併進這一條，見〈刻意保留抽查〉。持久化格式與 migration 依 CLAUDE.md 要先告知，由使用者拍板。 |
| A10 | 通過但修正 | `route_slug`（`jobs.py:288,1416` → `api/jobs.py:188`）、`link_bytes`、`source_bytes`（`deletion.py:92,96,136,139` → `api/jobs.py:284,288`）在 web/src 的產品程式碼零引用。`reclaimable` 由 `facts.reclaimable` 獨立算出（`deletion.py:140`），沒有用到這兩個欄位，所以刪掉不需要留局部變數。worker 漏列的消費點：`tests/integration/test_jobs_api.py:310` 斷言 `job["route_slug"]`；`test_deletion.py:489` 也用 `source_bytes`；前端 fixture 還有 `JobsPage.test.tsx:30,60`、`MediaDetailPage.test.tsx:35`、`SearchPanel.test.tsx:148`。`tests/e2e` 的 `route_slug` 是 payload 自己的欄位，和 API 無關。docs/ 沒有把這些欄位當成對外 API 記載。 | 建議不變。動到的檔要加上述測試檔與 fixture；`test_deletion.py:474,489` 可以改用 `held`、`reclaimable` 加上檔案大小來斷言。大小：小；風險：API 回應形狀（重新產生 `schema.d.ts`）。 |
| A11 | 駁回 | 下載列表（`jobs.py:100`）與媒體庫的牆（`inventory.py:94`）是兩個獨立可調的數。inventory 那一份的註解寫了自己的理由（M2 票 13 為了 DOM 節點數從 100 減半）；兩個 API 都把 `page_size` 回給前端，數字分岔也不會讓同一個判斷出現兩種答案。`jobs.py:99` 只是註記目前剛好相等。 | 不列發現。要改的話只是註解措辭，屬於風格。 |

## 待複核疑點結論

1. **`episode_end or episode_start` 散在各處、三種「同一集」**：不列發現。`end 缺省 = start` 是單集資料的表示慣例，散在 `LedgerEntry`、`PlanItem`、`ReleaseInfo`、`JellyfinItem` 這幾個不同型別上，都是一行；要長出不同答案，前提是有人改變「單集」的表示法，那會是資料格式變更，到時每處本來就要重看。三種判準是不同問題：`importer._same_episode`（`importer.py:425`）問「季同且範圍重疊」，用來把同一集的其他版本排回反查；`plan._duplicate_of`（`plan.py:708`）問「起始相同、結束不同」算衝突，「完全相同」算重複；`resolver.disagreement`（`resolver.py:301`）問「範圍相等」才算一致。語意本來就不同。小瑕疵：`_duplicate_of` 的 docstring 說「判準與同一包那一半共用 `parser.episode_span`」，但帳本那一側（`plan.py:727,735`）是行內算的，沒有呼叫 `episode_span`（它吃的是 `PlanItem`，不吃 `LedgerEntry`）。這是 docstring 措辭問題，不構成發現。
2. **deeplink 註解過期，與「沒選就當既有」規則多處**：註解確實過期。`health._origin` 在 `93af458`（`feat!: support only prowlarr…`）之後已經不存在，規則現在行內寫在 `health.py:486`（`setup.origin_of(kind) or ServiceOrigin.EXISTING`）。同一條規則「還沒選 = 既有」目前有：`routes._jellyfin_origin`（`routes.py:1308`）、`health.py:486` 行內、`deeplink.py:50`、`jellyfin.py:346,475` 的 `is not BUNDLED`、`qbittorrent._refuse_existing`（`qbittorrent.py:332`）、`indexer._refuse_existing`（`indexer.py:655`）、`setup.py:1059`。`ServiceOrigin` 目前只有兩個值，所以 `is not BUNDLED` 與 `(origin or EXISTING) is EXISTING` 等價；加第三種來源時這些地方會各說各話。**建議升格為低值發現**：在 `SetupSettings` 加一支「沒選當既有」的 accessor（例如 `origin_or_existing(kind)`），讓 routes 與 health 共用；`is not BUNDLED` 這幾處可以不動，因為它們問的是「是不是套件內」。deeplink 的註解改指 `routes._jellyfin_origin`。大小：小；風險：無。
3. **`Recorded.issue`**：依票規屬於「只有測試在用」：產品程式碼只讀 `.opened`（`reconcile.py:155`），`.issue` 只有 6 個測試檔讀（`test_issues.py:137,148`、`test_issues_api.py:90,346`、`test_ledger_gap.py:129`、`test_review.py:147`、`test_review_api.py:83`）。沒有註解寫明它是測試接縫。不過回傳「這次寫入或更新的那一列」本來就是命令結果的自然形狀（M5 命令登錄表要的也是結果），拿掉它會讓 6 個測試檔各自重查。結論：**成立但不值得做，建議不動**。如果要符合「刻意接縫」的標準，在 `Recorded` docstring 補一句即可。

## 刻意保留抽查

| 條目 | 出處是否寫了理由 | 結論 |
|---|---|---|
| `jobs.held_locks` | `jobs.py:227-229` docstring：「只給測試——用完就丟沒有別的觀測點」 | 成立 |
| `EventHub.subscribers` | `events.py:62` docstring：「健康頁與測試靠它確認訂閱真的收掉了」。但 grep 顯示 berth 與 web/src 都沒有健康頁在讀它，只有 `test_events.py`、`test_events_api.py` | 成立（屬測試接縫），docstring 裡「健康頁」那半句不實，見〈另外發現〉 |
| `commands.mark_of` | `test_command_marks.py` 的 docstring 與 CLAUDE.md 架構規則；另有 `test_setup_qbittorrent.py:149`、`test_setup_source.py:269,766,798,907` 在用；plan.md:986 的 M5 登錄表會讀標記 | 成立 |
| `qbittorrent.managed` / `unknown_torrents` / `unknown_torrent_detail` | `qbittorrent.py:83-85`、`:94-96`、`:112-114` 都寫「只有一份／兩個生產者寫同一份」 | 成立 |
| 兩個 `_refuse_existing` | 註解只寫了紅線的出處（brief §16.4），**沒有寫為什麼各留一份**；兩者的述詞相同（`is not BUNDLED`），只是訊息不同 | 出處不成立。實質上可以併進待複核疑點 2 的「沒選當既有」規則群；兩支各留也只是訊息不同的守衛，值得度很低 |
| `review.py` 四組 `_count_*` / `_fetch_*` / `_*_row` | `review.py:499-726` 四組的查詢與列型別各不相同 | 成立（不是同一件事，屬「不算發現」，不必靠出處） |
| `bench.py` 動態存取的欄位 | `bench.py:129` 註解「以下八格與 `Bucket` 同名同義」；`GUARDED`（`bench.py:351`）以字串取；`_COLUMNS` 以 `Bucket` 值展開（`bench.py:404`） | 成立 |
| `LedgerEntry.source_inode` | `models/ledger.py:57` 只定義「與 `target_inode` 相等就是硬鏈接成立」，產品程式碼沒有任何地方比對它。寫入有 `claims.py:359`、`importer.py:373`、`issues.py:379,475`，讀取只有 `test_importer.py:229,231`；`deletion.py:368` 用的是 `source_dev` 加 `target_inode` | 出處不成立：那是欄位定義，不是保留理由。應與 A9 同樣處理（只寫不讀、由使用者決定），worker 前後標準不一致 |
| discover / media / sources 三種 TTL | `sources.py` 模組 docstring（兩小時、程序內、不落地）、`media.py:62,67`（24h／6h）、`discover.py:39`（1h，落地到 `TmdbCache`） | 成立：存的東西與過期語意都不同 |

## 工具判定抽查

抽了 18 條「誤報」，逐條確認欄位經 `berth/api` 序列化，並且 web/src 的非測試、非 `schema.d.ts` 檔確實有讀：

| 項目 | 自己查到的讀取點 | 結論 |
|---|---|---|
| health.py:120 `interval_seconds` | `web/src/health/PollerCard.tsx:41` | 誤報正確 |
| jobs.py:290 `user_name` | `web/src/pages/JobDetailPage.tsx:99` | 誤報正確 |
| qbittorrent.py:158 `webapi_version` | `web/src/setup/QbittorrentStep.tsx:161-162` | 誤報正確 |
| rss.py:193 `ever_read` | `web/src/rss/FirstRoundSection.tsx:91` | 誤報正確 |
| bangumi.py:33 `bound_to` | `web/src/media/SubscribePanel.tsx:329-333` | 誤報正確 |
| first_batch.py:77 `basis` | `web/src/rss/firstBatchAsk.ts:26`（`ask.basis`）；`api/schemas.py:351` | 誤報正確，但 worker 寫「前端 7 個檔讀」是把 CSS 的 `basis-full` 也算進去，實際只有 1 個檔 |
| indexer.py:166 / qbittorrent.py:173 `web_ui_login_by_berth` | `web/src/setup/ServiceDoors.tsx:107-111` | 誤報正確 |
| jellyfin.py:214 `bundled_default` | `web/src/setup/autoDock.ts:15` | 誤報正確 |
| routes.py:179 `has_route` | `web/src/setup/RouteStep.tsx:164,297,330,732` | 誤報正確 |
| setup.py:151 `owner_signs_in` | `web/src/setup/OwnerStep.tsx:164` | 誤報正確 |
| watch.py:29 `unplayed_episodes` | `web/src/components/watchLine.ts:14-15` | 誤報正確 |
| search.py:215 `next_seasons` | `web/src/media/SearchPanel.tsx:457-467` | 誤報正確 |
| plan_view.py:62 `applied` | `web/src/plans/PlanEditor.tsx:141`（`item.applied`） | 誤報正確 |
| qbittorrent.py:162 `blocked` | `web/src/pages/SetupPage.tsx:857`（`setup?.blocked`） | 誤報正確 |
| routes.py:162 `probe_carried` | `web/src/components/RouteCheckList.tsx` | 誤報正確 |
| setup.py:137 `waited_seconds` | `web/src/settings/JellyfinConnection.tsx`、`setup/ServiceChoice.tsx` | 誤報正確 |
| setup.py:157 `window_seconds` | 同上兩檔等 4 檔 | 誤報正確 |
| rss.py:246 `latest_episode` | `web/src/rss/SeriesSection.tsx` | 誤報正確 |

bench.py 的六條（`confidence_met`、`unmatched_correct`、`extra_correct`、`subtitle_correct`、`Baseline.*`）也對照了 `bench.py:129-136`、`351`、`356-367`、`404-446`，屬動態或字串存取，誤報判定正確。

## 複核者另外發現

1. **`EventHub.subscribers` 的 docstring 不實**（`events.py:62-63`）：docstring 說健康頁靠它，但 grep `subscribers` 在 berth 與 web/src 只有定義處，讀取都在 tests。它不是死碼，因為測試接縫成立，但 docstring 的半句宣稱沒有消費者。建議改成「只給測試」。大小：極小。
2. **「還沒選就當既有」規則多處**：見待複核疑點 2。建議列為低值發現：`routes._jellyfin_origin` 與 `health.py:486` 合成 `SetupSettings` 上的一支；deeplink 的過期註解一起修。
3. **`LedgerEntry.source_inode` 只寫不讀**：應從「刻意保留」移進 A9，與 `last_seen_in_client_at` 等欄位一起交使用者決定（證據見上表）。
4. **`owning_route` 在不正規路徑上的「最深」量法**：見 A6 修正。真正有潛在錯誤的是 `routes.owning_route`，它用字串長度；`claims._route_of` 用路徑段數，是對的那一份。合併時要以 claims 的量法為準，並補測試。
