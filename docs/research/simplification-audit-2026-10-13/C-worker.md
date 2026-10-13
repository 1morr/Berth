# C adapters / api / pipeline / 頂層

方法摘要：用 `app.openapi()` 取全部路由，逐條對 `web/src`（非測試）、`web/e2e`、`cli.py`、`scripts/` 做路徑比對，**每一條端點都至少有一個前端消費者**（沒有只有測試打的端點）。回應欄位則把 OpenAPI 每個 `*Out` 的每個欄位拿去 grep 前端非測試、非 `schema.d.ts` 的讀取點。adapters 另外用 AST 掃過「類別方法 / `__all__` 名稱在 adapters 之外的呼叫數」。

## 發現

### C1 `GET /settings/services` 與 `GET /health/detail` 是同一份答案的兩個端點
- 類別：重複
- 是什麼：兩支都是 `health_detail(await read_health(session))`，回 `HealthDetailOut`（`berth/api/settings.py:45-48`、`berth/api/health.py:53-56`）。前端各有一組 query（`web/src/api/settings.ts:17` 的 `servicesQueryOptions` 與 `web/src/api/health.ts:19` 的 `healthDetailQueryOptions`），`web/src/settings/useServiceCheck.ts:20-21` 每次重測要把同一份資料 `setQueryData` 寫進兩把 key，否則兩邊不同步。唯一差別是門禁：前者 admin、後者登入即可；但設定頁本來就只有 admin 進得來。
- 證據：`settings.py` 的 docstring 自己寫「與健康頁同一份形狀——同一件事不該有兩種說法」；`servicesQueryOptions` 只有 `settings/HealthSection.tsx:17` 與 `useServiceCheck.ts` 用。progress.md 沒有記要分兩支的理由（`docs/progress.md:36` 只記新增、`docs/plan.md:391` 記形狀相同）。
- 建議：保留 `GET /health/detail`，刪 `GET /settings/services` 與 `servicesQueryOptions`，`HealthSection` / `useServiceCheck` 改用 `healthDetailQueryOptions`（少一把要手動同步的 key）。`POST /settings/services/{kind}/test` 留著。
- 大小：小（兩個後端檔、三個前端檔、對應測試、重跑 `gen:api`、改 `docs/plan.md:391`）
- 風險：動到對外 API（刪一個 GET，只有自家前端用）；不動持久化、不 migration。
- 值得度：高。純粹的一事兩名，且前端為此維護雙 key 同步。

### C2 `JellyfinSetupOut.libraries: list[LibraryOut]` 前端完全沒讀
- 類別：沒人用（API 回應欄位）
- 是什麼：`berth/api/setup.py:454-464` 的 `LibraryOut`（`name / collection_type / locations / metadata_fetchers / uses_tvdb / berth_path / has_berth_path`）只掛在 `JellyfinSetupOut.libraries`（`setup.py:498`）。頁 3 的媒體庫清單前端讀的是 `RouteSetupOut.libraries: list[LibraryChoiceOut]`（`setup.py:949-964`，`RouteStep.tsx:163,186,441,800`），欄位大半相同（name / collection_type / locations / berth_path / has_berth_path / uses_tvdb）。
- 證據：`web/src` 沒有任何對 `JellyfinSetup` 的 `.libraries` 讀取；`metadata_fetchers` 在前端只出現在 `web/src/test/fixtures.ts:119`。vulture 把 `setup.py:461`、`:463` 判成沒人用即由此而來。後端只有 `tests/integration/test_setup_api.py:629,692-694` 在斷言它；`services/routes.py:222,848` 讀的是 `setup.jellyfin.libraries`（資料庫快照），不是這個 API 欄位。
- 建議：從 `JellyfinSetupOut` 拿掉 `libraries` 與 `LibraryOut`，測試改斷言 `RouteSetupOut`；services 的快照照舊。
- 大小：小
- 風險：動到 API 回應形狀（前端沒讀；需重跑 `gen:api`、更新 `src/test/fixtures.ts`）；不動持久化。
- 值得度：中。整個沒人讀的 7 欄子模型，但只是回應多帶，不影響邏輯。

### C3 「精靈跑完了沒」三個出口：`/health.setup_completed`、`/setup/status.completed`、`/setup/routes.completed`
- 類別：重複（同一個事實多個出口）
- 是什麼：前端守衛只讀 `Health.setup_completed`（`web/src/routes.tsx:74`；`SetupPage.tsx:394` 完成後只改這一把快取）。`SetupStatusOut.completed`（`berth/api/setup.py:143`）與 `RouteSetupOut.completed`（`setup.py` 的 `RouteSetupOut`，約 `:974`）前端不讀。`api/health.py:36-38` 的註解甚至說明這個決定「必須掛在匿名端點上，不在 `setup/status`」。
- 證據：`grep -rnw completed web/src`（排除 jobs / 測試 / i18n）只剩 `routes.tsx` 的 `gate.completed`（來自 health）；後端 `tests/integration/test_setup_api.py:98,1275` 斷言它。
- 建議：以 `/health` 為唯一出口，刪 `SetupStatusOut.completed` 與 `RouteSetupOut.completed`（services 內部的 `SetupStatus.completed` 仍用得上，只拿掉 API 欄位）。
- 大小：小
- 風險：API 回應形狀（前端沒讀）。
- 值得度：低。兩個多帶的布林值；但留著會讓下一個人以為前端有兩個來源。

### C4 其他 API 回應欄位前端沒讀（逐欄 grep 為零）
- 類別：沒人用（API 回應欄位）
- 是什麼：
  - `DeletionEstimateOut.link_bytes`、`source_bytes`（`berth/api/jobs.py:284,288`）：docstring 還特地說 `reclaimable` 不是兩者之和，前端只讀 `reclaimable` / `held` / `links` / `sources`（`JobDelete.tsx:193-216`）。services 的 `DeletionEstimate.link_bytes/source_bytes`（`services/deletion.py:92,96,136,139`，跨區）是來源。
  - `JobOut.route_slug`（`jobs.py:188`；來源 `services/jobs.py:288,1416`，跨區）、`trigger_ref`、`user_id`、`content_path`、`completed_at`、`imported_at`。
  - `PlanOut.engine`、`engine_version`（含 `PlanEditedOut`，`plans.py:170-172`）。
  - `BudgetOut.window_seconds`（`health.py:97`）、`SiteBudgetOut.frees_at`、`DeferralOut.since`。
  - `ItemOut.seen_at`（`rss.py:298`）、`BangumiOut.premiere`（`rss.py:590`）、`UnmatchedRowOut.file_kind`（`review.py:213,480`）。
- 證據：`web/src` 非測試、非 `schema.d.ts`、非 i18n 的欄位名 word-match 皆為 0；`window_seconds` 另行確認 `BudgetCard.tsx:22` 只解構 `{ limit, sites }`。其中 `engine*`、`content_path`、`trigger_ref` 是資料庫欄位直通，後端測試與 services 有用。
- 建議：從 `*Out` 拿掉不給畫面用的欄位（services 欄位與資料庫不動）；`link_bytes/source_bytes` 若只為了算 `reclaimable`，可留在 services 內部不上 API。未來要用再加。
- 大小：中（欄位多但每個一行；各 router + 前端 fixtures + 重跑 `gen:api`）
- 風險：API 回應形狀（只有自家前端消費）；不動持久化。
- 值得度：低-中。零邏輯風險，收益是 API 表面變小；`engine*`、`trigger_ref` 可能是刻意留給 M5 / 除錯，**需使用者決定**（progress.md 沒找到理由）。

### C5 qBittorrent 自己一份版本字串解析，`adapters/versions.parse_version` 已經有了
- 類別：重複
- 是什麼：`berth/adapters/qbittorrent/__init__.py:587-595` 的 `_parse` 與 `berth/adapters/versions.py:9-17` 的 `parse_version` 做同一件事（`"2.8.5"` → tuple）。`versions.py` docstring 寫「Jellyfin 與 Prowlarr 的版本下限共用」，qBittorrent 沒接上。差別只在無法解析時：`_parse` 回 `()`、`parse_version` 回 `(0,)`，對下限比較結果相同（都小於 `MIN_WEBAPI`）。`qbittorrent/__init__.py:81,86,94` 三處使用。
- 證據：`grep -rn "parse_version" berth`：jellyfin、prowlarr 用；`_parse` 只有這三處呼叫。
- 建議：qBittorrent 改用 `parse_version`，刪 `_parse`。
- 大小：小（一個檔、3 行；跑 qBittorrent 版本相關測試）
- 風險：無對外介面變動。
- 值得度：中。典型「同一件事兩份實作」，改動極小。

### C6 pipeline 七個迴圈各抄一份 `run()` 骨架；`Sleeper` / `Clock` 別名重複；`Waiter` 沒人用
- 類別：重複 + 沒人用
- 是什麼：
  - `downloads.py:81-90`、`health.py:60-68`、`importing.py:52-59`、`planning.py:62-72`、`reconciling.py:72-80`、`resolving.py:39-45`、`rss.py:49-56` 都是 `while True: await 等待; try: await whole_tick(...) except Exception: logger.exception("... failed")`，加上每個 tick 開頭 `async with sessions: if not await is_setup_complete(session): return …`（七處）。`pipeline/ticks.py` 的 `whole_tick` 只抽出了中間那一句。
  - `Sleeper = Callable[[float], Awaitable[None]]` 在 `downloads.py:51`、`health.py:32`、`reconciling.py:37`、`rss.py:27` 各定義一次；`Clock = Callable[[], datetime]` 同四處，再加 `adapters/budget.py:30` 與 `services/indexer.py:92`（Sleeper，跨區）。
  - `pipeline/planning.py:34` 的 `Waiter` 全 repo 零引用。
- 證據：上列行號；`grep -rn "Waiter" berth tests` 只有定義。註解（`rss.py` 檔頭「與 health_checker 同一個形狀」、`importing.py`「與 planner_runner 同一個形狀」）只說明相似，沒有說為什麼不共用；progress.md 沒查到相關偏差。
- 建議：最低限度——刪 `Waiter`、把 `Sleeper`/`Clock` 收到 `pipeline/ticks.py`。想再簡化——在 `ticks.py` 加一個 `loop(wait, tick, name)` 把 while/try/except/log 收成一份（`reconciling.run_if_due` 的順序特殊，需個別看）。
- 大小：別名與 `Waiter` 小；收迴圈骨架中（7 個檔 + `tests/integration/test_loop_shutdown.py` 等）。
- 風險：不動對外介面。關機語意（`whole_tick`）靠既有的 `test_loop_shutdown.py` 守。
- 值得度：別名 / `Waiter` 中（便宜）；迴圈骨架低-中（七份完全一樣但各 10 行，抽象會多一層間接）。

### C7 API 層樣板：`actor_of(user.id if user is not None else None)` 與 `JellyfinWebOut.model_validate(await jellyfin_web(...))` 各被抄多次
- 類別：重複
- 是什麼：
  - 「這個請求的操作者」：`plans.py:298-300` 有 `_actor(request)`；但 `files.py:146-153`、`issues.py:235-261`（2 處）、`jobs.py:345,439-442,504-516`（3 處）、`review.py:331-404`（5 處）各自內聯同一句 `current_user(request)` + `actor_of(user.id if user is not None else None)`，共約 12 處（`rss.py:518,678,708` 取 `user.id` 的變體另算）。
  - `JellyfinWebOut.model_validate(await jellyfin_web(session, published_port=config.jellyfin_port))` 在 `inventory.py:228`、`jellyfin.py:186`、`media.py:316`、`settings.py:68` 各一份。
- 證據：`grep -n "actor_of(user.id" berth/api/*.py`；`grep -n "jellyfin_web(" berth/api/*.py`。
- 建議：把 `plans._actor` 移到 `api/gate.py`（旁邊就是 `current_user`）成為共用函式，各處改用；`JellyfinWebOut` 那段收成 `api/schemas.py` 內一個 `jellyfin_web_out(session, config)`。
- 大小：小
- 風險：無對外介面變動。
- 值得度：中。機械式、行為不變，且讓「沒登入者算 system」只剩一個地方決定。

### C8 `Config.data_root` 產品碼沒有人讀
- 類別：沒人用（設定欄位）
- 是什麼：`berth/config.py:40,65` 的 `data_root`（環境變數 `DATA_ROOT`，`deploy/Dockerfile:46` 也設了 `DATA_ROOT=/data`）。產品碼裡 Berth 的共用根目錄來自資料庫的 `PathSettings`（`models/setting.py:138-143` 寫死 `/data/...`；`services/setup.py:763-765 _data_root` 讀它）。`Config.data_root` 只有 `tests/unit/test_config.py:24,58,99` 與 dev 腳本 `scripts/fake_setup_server.py:2029` 讀。
- 證據：`grep -rn "\.data_root" berth` 沒有 `Config` 的讀取（只有 `services/setup.py` 的區域參數 `data_root`）。
- 建議：移除 `Config.data_root` / `DATA_ROOT` 讀取（compose 主機端的 `${DATA_ROOT}` 掛載與 `.env.example` 不動，那是另一個東西）；`fake_setup_server.py` 自己給常數。
- 大小：小
- 風險：容器 ENV 的 `DATA_ROOT=/data` 現況本來就沒有作用，行為不變；仍屬設定項變動，需同步 CHANGELOG / `docs/development.md`（若有記）。
- 值得度：低。

### C9 `IndexerResult.leechers` 與 `FakeIndexerSearch.closed` 沒有讀取者
- 類別：沒人用
- 是什麼：`berth/adapters/indexer/__init__.py:56` `leechers` 由 `indexer/prowlarr.py:94` 填入；`services/search.py:107,661`、`api/search.py:64` 的搜尋結果只帶 `seeders`；唯一讀它的是 `tests/integration/test_indexer_search.py:44`。`berth/adapters/indexer/fake.py:40,65` 的 `closed` 有寫無讀。
- 證據：`grep -rn "\.leechers" berth` 無；`grep -rnw closed tests` 在 indexer 脈絡下無斷言。
- 建議：刪 `leechers`（欄位、填值、該測試斷言）；刪 `FakeIndexerSearch.closed`。
- 大小：小
- 風險：無。
- 值得度：低。

### C10 兩個「這支端點不存在」的否定測試
- 類別：沒人用（只守著不存在的介面）
- 是什麼：`tests/integration/test_media_api.py:128-134 test_there_is_no_track_endpoint`（POST `/api/media/{id}/track` 回 404）與 `tests/integration/test_setup_api.py:1067`（POST `/api/setup/tmdb/skip` 回 404，註解寫「這一支不存在了」）。門禁測試（`test_auth_api.py:598-605`）已有「新路由沒登記就紅」的通則。
- 證據：上列檔案行；`/media/*/track`、`/setup/tmdb/skip` 不在 OpenAPI。
- 建議：刪這兩條斷言；「不存在」由 `test_openapi_contract` 與門禁表的雙向檢查涵蓋。
- 大小：小
- 風險：無。
- 值得度：低。

## 刻意保留
- `adapters/ai.py` 的 `AiPlanner` / `NullAiPlanner`：產品碼零呼叫，只有 `tests/unit/test_ai.py`；`docs/plan.md:322` 明寫「介面在 M1 就定好…至今沒有呼叫端」，是 M5 AI 任務核心。
- 各 router 的 `XRefusalOut` + `_STATUS` + `_refusals()` / `x_refusal()` 樣板（files / issues / jellyfin / jobs / plans / review / routes / rss / setup×4，約 12 組）：看起來重複，但 `docs/progress.md:84`（M2 票 02）記載刻意「每個拒絕 enum 一個 model」讓 OpenAPI 產出封閉集合，`tests/unit/test_openapi_contract.py` 以函式名為鍵守著（見 `berth/api/files.py:194-200` 的註解）。要收須連契約測試一起改，不列為發現。
- `AuditReasonOut` / `PlanReasonOut` / `UnmatchedReasonOut` / `DuplicateReasonOut`（`review.py:101-225`）形狀相同（`code` + `params`）：同上，各用自己的 enum 當 `code`。
- `GET /jellyfin/libraries`（`LibraryOptionOut`）與 `POST /setup/routes/libraries`（`LibraryChoiceOut`）兩套媒體庫清單：`docs/progress.md:871`（票 14）決定新增 Route 時向 Jellyfin 現查、不讀頁 3 的快照。
- `berth rebuild-ledger` CLI 與 `POST /issues/rebuild-ledger`：`docs/plan.md:866` 與 `docs/progress.md:203`（M4 票 60）寫明兩個入口。
- 三條 confirm 端點（`/review/audit/{id}/confirm`、`/audit/confirm`、`/series/{id}/confirm`）：單一版有 409 拒絕、批次版是跳過（`review.py:341-354` docstring），語意不同。
- `/settings/services/{kind}/test`、`/setup/services/{kind}/test`、`/health/check`：回傳形狀與範圍不同（設定頁單一服務 / 精靈用存下的選擇重測 / 全部重跑）；`web/src/api/settings.ts` 頂端註解與 `docs/progress.md:118` 說明設定頁沿用 `setup/*` 命令。
- `adapters/*/fake.py` 的公開介面（`revoke_api_key`、`signs_in`、`calls`、`syncs`、`LIBRARY_SCAN_TASK`…）逐一核對都有測試呼叫，不列。
- `adapters/http.py` 的例外類別：每個都有 services 分支（各 docstring 說明下一步不同）。
- `api/gate.py:238-239` 與 `_admin_verdict`（`:245-248`）的「非 admin 就 403」：安全門禁，各自帶不同的 401 / 403 訊息，不動。

## 待複核疑點
- `docs/plan.md:52` 寫 `cli.py` 有 `berth reconcile`，實際 `berth/cli.py:37-87` 只有 `serve / openapi / bench / rebuild-ledger`。不確定是文件過時還是子指令被拿掉（文件偏差，不是程式碼）。
- C4 的 `engine` / `engine_version` / `trigger_ref` 是否為 M5 或除錯用：progress.md 找不到理由，故列為「待使用者決定」。
- `adapters/qbittorrent/__init__.py` 的 `__all__` 有 5 個常數（`METADATA_PENDING_STATE`、`PRIORITY_SKIP`、`SETTLING_STATES`、`STALLED_STATE`、`STOPPED_SINCE_WEBAPI`）及 `torrent.MAX_TORRENT_BYTES`、`tmdb.ABSOLUTE_GROUP_TYPE` 只在自己模組內用卻匯出。屬過度匯出而非死碼，沒有列為發現。

## 工具結果判定
| 位置 | 項目 | 判定 | 理由 |
|---|---|---|---|
| `berth/adapters/http.py:125` | variable `exc_type`（連測試都沒用） | 誤報 | `__aexit__` 協定簽章必須的參數 |
| `berth/adapters/http.py:127` | variable `tb`（連測試都沒用） | 誤報 | `__aexit__` 協定簽章必須的參數 |
| `berth/adapters/rss/mikan.py:143` | method `handle_starttag`（連測試都沒用） | 誤報 | `HTMLParser` 回呼，由基底類別呼叫 |
| `berth/adapters/rss/mikan.py:205` | method `handle_starttag`（連測試都沒用） | 誤報 | `HTMLParser` 回呼，由基底類別呼叫 |
| `berth/adapters/rss/mikan.py:213` | method `handle_endtag`（連測試都沒用） | 誤報 | `HTMLParser` 回呼，由基底類別呼叫 |
| `berth/adapters/rss/mikan.py:220` | method `handle_data`（連測試都沒用） | 誤報 | `HTMLParser` 回呼，由基底類別呼叫 |
| `berth/adapters/rss/mikan.py:262` | method `handle_starttag`（連測試都沒用） | 誤報 | `HTMLParser` 回呼，由基底類別呼叫 |
| `berth/adapters/rss/mikan.py:275` | method `handle_endtag`（連測試都沒用） | 誤報 | `HTMLParser` 回呼，由基底類別呼叫 |
| `berth/adapters/rss/mikan.py:331` | method `handle_starttag`（連測試都沒用） | 誤報 | `HTMLParser` 回呼，由基底類別呼叫 |
| `berth/adapters/rss/mikan.py:351` | method `handle_data`（連測試都沒用） | 誤報 | `HTMLParser` 回呼，由基底類別呼叫 |
| `berth/adapters/rss/mikan.py:355` | method `handle_endtag`（連測試都沒用） | 誤報 | `HTMLParser` 回呼，由基底類別呼叫 |
| `berth/api/discover.py:24` | variable `model_config`（連測試都沒用） | 誤報 | pydantic `model_config` 由框架讀取 |
| `berth/api/events.py:64` | variable `media_type`（連測試都沒用） | 誤報 | FastAPI 讀它決定 OpenAPI 的 content type（註解 events.py:58-63） |
| `berth/api/inventory.py:64` | variable `model_config`（連測試都沒用） | 誤報 | pydantic `model_config` 由框架讀取 |
| `berth/api/inventory.py:80` | variable `has_imports`（連測試都沒用） | 誤報 | pydantic 回應欄位，auth/destination.ts:44 讀 |
| `berth/api/inventory.py:86` | variable `model_config`（連測試都沒用） | 誤報 | pydantic `model_config` 由框架讀取 |
| `berth/api/inventory.py:95` | variable `model_config`（連測試都沒用） | 誤報 | pydantic `model_config` 由框架讀取 |
| `berth/api/inventory.py:112` | variable `model_config`（連測試都沒用） | 誤報 | pydantic `model_config` 由框架讀取 |
| `berth/api/jobs.py:168` | variable `model_config`（連測試都沒用） | 誤報 | pydantic `model_config` 由框架讀取 |
| `berth/api/jobs.py:191` | variable `user_name`（連測試都沒用） | 誤報 | pydantic 回應欄位，JobDetailPage.tsx:99 讀 |
| `berth/api/jobs.py:204` | variable `retryable`（連測試都沒用） | 誤報 | pydantic 回應欄位，jobs/JobActions.tsx:47 讀 |
| `berth/api/jobs.py:284` | variable `link_bytes`（連測試都沒用） | 真的沒人用 | 前端 `web/src` 沒讀（JobDelete 只讀 `reclaimable`、`links`、`links_missing`…），見 C4 |
| `berth/api/jobs.py:320` | variable `model_config`（連測試都沒用） | 誤報 | pydantic `model_config` 由框架讀取 |
| `berth/api/media.py:54` | variable `model_config`（連測試都沒用） | 誤報 | pydantic `model_config` 由框架讀取 |
| `berth/api/media.py:74` | variable `model_config`（連測試都沒用） | 誤報 | pydantic `model_config` 由框架讀取 |
| `berth/api/media.py:95` | variable `model_config`（連測試都沒用） | 誤報 | pydantic `model_config` 由框架讀取 |
| `berth/api/media.py:106` | variable `model_config`（連測試都沒用） | 誤報 | pydantic `model_config` 由框架讀取 |
| `berth/api/media.py:135` | variable `model_config`（連測試都沒用） | 誤報 | pydantic `model_config` 由框架讀取 |
| `berth/api/media.py:152` | variable `model_config`（連測試都沒用） | 誤報 | pydantic `model_config` 由框架讀取 |
| `berth/api/media.py:167` | variable `model_config`（連測試都沒用） | 誤報 | pydantic `model_config` 由框架讀取 |
| `berth/api/media.py:183` | variable `model_config`（連測試都沒用） | 誤報 | pydantic `model_config` 由框架讀取 |
| `berth/api/media.py:259` | variable `model_config`（連測試都沒用） | 誤報 | pydantic `model_config` 由框架讀取 |
| `berth/api/plans.py:111` | variable `model_config`（連測試都沒用） | 誤報 | pydantic `model_config` 由框架讀取 |
| `berth/api/plans.py:120` | variable `model_config`（連測試都沒用） | 誤報 | pydantic `model_config` 由框架讀取 |
| `berth/api/plans.py:154` | variable `model_config`（連測試都沒用） | 誤報 | pydantic `model_config` 由框架讀取 |
| `berth/api/plans.py:164` | variable `model_config`（連測試都沒用） | 誤報 | pydantic `model_config` 由框架讀取 |
| `berth/api/review.py:140` | variable `model_config`（連測試都沒用） | 誤報 | pydantic `model_config` 由框架讀取 |
| `berth/api/review.py:297` | variable `issues_open`（連測試都沒用） | 誤報 | pydantic 回應欄位，ReviewPage.tsx:121 讀 |
| `berth/api/routes.py:103` | variable `model_config`（連測試都沒用） | 誤報 | pydantic `model_config` 由框架讀取 |
| `berth/api/routes.py:113` | variable `model_config`（連測試都沒用） | 誤報 | pydantic `model_config` 由框架讀取 |
| `berth/api/rss.py:105` | variable `model_config`（連測試都沒用） | 誤報 | pydantic `model_config` 由框架讀取 |
| `berth/api/rss.py:126` | variable `ever_read`（連測試都沒用） | 誤報 | pydantic 回應欄位，FirstRoundSection.tsx:91 讀 |
| `berth/api/rss.py:146` | variable `model_config`（連測試都沒用） | 誤報 | pydantic `model_config` 由框架讀取 |
| `berth/api/rss.py:165` | variable `model_config`（連測試都沒用） | 誤報 | pydantic `model_config` 由框架讀取 |
| `berth/api/rss.py:182` | variable `model_config`（連測試都沒用） | 誤報 | pydantic `model_config` 由框架讀取 |
| `berth/api/rss.py:191` | variable `model_config`（連測試都沒用） | 誤報 | pydantic `model_config` 由框架讀取 |
| `berth/api/rss.py:201` | variable `model_config`（連測試都沒用） | 誤報 | pydantic `model_config` 由框架讀取 |
| `berth/api/rss.py:264` | variable `model_config`（連測試都沒用） | 誤報 | pydantic `model_config` 由框架讀取 |
| `berth/api/rss.py:284` | variable `model_config`（連測試都沒用） | 誤報 | pydantic `model_config` 由框架讀取 |
| `berth/api/rss.py:291` | variable `model_config`（連測試都沒用） | 誤報 | pydantic `model_config` 由框架讀取 |
| `berth/api/rss.py:324` | variable `model_config`（連測試都沒用） | 誤報 | pydantic `model_config` 由框架讀取 |
| `berth/api/rss.py:350` | variable `model_config`（連測試都沒用） | 誤報 | pydantic `model_config` 由框架讀取 |
| `berth/api/rss.py:563` | variable `model_config`（連測試都沒用） | 誤報 | pydantic `model_config` 由框架讀取 |
| `berth/api/rss.py:571` | variable `model_config`（連測試都沒用） | 誤報 | pydantic `model_config` 由框架讀取 |
| `berth/api/rss.py:586` | variable `model_config`（連測試都沒用） | 誤報 | pydantic `model_config` 由框架讀取 |
| `berth/api/rss.py:610` | variable `model_config`（連測試都沒用） | 誤報 | pydantic `model_config` 由框架讀取 |
| `berth/api/schemas.py:35` | variable `model_config`（連測試都沒用） | 誤報 | pydantic `model_config` 由框架讀取 |
| `berth/api/schemas.py:50` | variable `model_config`（連測試都沒用） | 誤報 | pydantic `model_config` 由框架讀取 |
| `berth/api/schemas.py:106` | variable `model_config`（連測試都沒用） | 誤報 | pydantic `model_config` 由框架讀取 |
| `berth/api/schemas.py:112` | variable `webapi_version`（連測試都沒用） | 誤報 | pydantic 回應欄位，QbittorrentStep.tsx 讀 |
| `berth/api/schemas.py:130` | variable `web_port`（連測試都沒用） | 誤報 | pydantic 回應欄位，setup/serviceWeb.ts 讀 |
| `berth/api/schemas.py:143` | variable `model_config`（連測試都沒用） | 誤報 | pydantic `model_config` 由框架讀取 |
| `berth/api/schemas.py:172` | variable `model_config`（連測試都沒用） | 誤報 | pydantic `model_config` 由框架讀取 |
| `berth/api/schemas.py:185` | variable `model_config`（連測試都沒用） | 誤報 | pydantic `model_config` 由框架讀取 |
| `berth/api/schemas.py:193` | variable `interval_seconds`（連測試都沒用） | 誤報 | pydantic 回應欄位，PollerCard.tsx:41、HealthPage.tsx:83 讀 |
| `berth/api/schemas.py:200` | variable `model_config`（連測試都沒用） | 誤報 | pydantic `model_config` 由框架讀取 |
| `berth/api/schemas.py:206` | variable `interval_seconds`（連測試都沒用） | 誤報 | pydantic 回應欄位，PollerCard.tsx:41、HealthPage.tsx:83 讀 |
| `berth/api/schemas.py:222` | variable `model_config`（連測試都沒用） | 誤報 | pydantic `model_config` 由框架讀取 |
| `berth/api/schemas.py:253` | variable `model_config`（連測試都沒用） | 誤報 | pydantic `model_config` 由框架讀取 |
| `berth/api/schemas.py:290` | variable `model_config`（連測試都沒用） | 誤報 | pydantic `model_config` 由框架讀取 |
| `berth/api/schemas.py:314` | variable `still_url`（連測試都沒用） | 誤報 | pydantic 回應欄位，media/WatchArea.tsx:281 讀 |
| `berth/api/schemas.py:337` | variable `model_config`（連測試都沒用） | 誤報 | pydantic `model_config` 由框架讀取 |
| `berth/api/schemas.py:348` | variable `model_config`（連測試都沒用） | 誤報 | pydantic `model_config` 由框架讀取 |
| `berth/api/search.py:40` | variable `model_config`（連測試都沒用） | 誤報 | pydantic `model_config` 由框架讀取 |
| `berth/api/search.py:55` | variable `model_config`（連測試都沒用） | 誤報 | pydantic `model_config` 由框架讀取 |
| `berth/api/search.py:94` | variable `model_config`（連測試都沒用） | 誤報 | pydantic `model_config` 由框架讀取 |
| `berth/api/search.py:133` | variable `model_config`（連測試都沒用） | 誤報 | pydantic `model_config` 由框架讀取 |
| `berth/api/search.py:146` | variable `model_config`（連測試都沒用） | 誤報 | pydantic `model_config` 由框架讀取 |
| `berth/api/setup.py:108` | variable `model_config`（連測試都沒用） | 誤報 | pydantic `model_config` 由框架讀取 |
| `berth/api/setup.py:141` | variable `model_config`（連測試都沒用） | 誤報 | pydantic `model_config` 由框架讀取 |
| `berth/api/setup.py:269` | variable `resolvable`（連測試都沒用） | 誤報 | pydantic 回應欄位，api/setup.ts:56 讀 |
| `berth/api/setup.py:372` | variable `model_config`（連測試都沒用） | 誤報 | pydantic `model_config` 由框架讀取 |
| `berth/api/setup.py:382` | variable `model_config`（連測試都沒用） | 誤報 | pydantic `model_config` 由框架讀取 |
| `berth/api/setup.py:455` | variable `model_config`（連測試都沒用） | 誤報 | pydantic `model_config` 由框架讀取 |
| `berth/api/setup.py:469` | variable `model_config`（連測試都沒用） | 誤報 | pydantic `model_config` 由框架讀取 |
| `berth/api/setup.py:481` | variable `model_config`（連測試都沒用） | 誤報 | pydantic `model_config` 由框架讀取 |
| `berth/api/setup.py:492` | variable `model_config`（連測試都沒用） | 誤報 | pydantic `model_config` 由框架讀取 |
| `berth/api/setup.py:684` | variable `model_config`（連測試都沒用） | 誤報 | pydantic `model_config` 由框架讀取 |
| `berth/api/setup.py:702` | variable `model_config`（連測試都沒用） | 誤報 | pydantic `model_config` 由框架讀取 |
| `berth/api/setup.py:714` | variable `model_config`（連測試都沒用） | 誤報 | pydantic `model_config` 由框架讀取 |
| `berth/api/setup.py:727` | variable `model_config`（連測試都沒用） | 誤報 | pydantic `model_config` 由框架讀取 |
| `berth/api/setup.py:753` | variable `web_port`（連測試都沒用） | 誤報 | pydantic 回應欄位，setup/serviceWeb.ts 讀 |
| `berth/api/setup.py:779` | variable `model_config`（連測試都沒用） | 誤報 | pydantic `model_config` 由框架讀取 |
| `berth/api/setup.py:791` | variable `model_config`（連測試都沒用） | 誤報 | pydantic `model_config` 由框架讀取 |
| `berth/api/setup.py:918` | variable `model_config`（連測試都沒用） | 誤報 | pydantic `model_config` 由框架讀取 |
| `berth/api/setup.py:950` | variable `model_config`（連測試都沒用） | 誤報 | pydantic `model_config` 由框架讀取 |
| `berth/api/setup.py:968` | variable `model_config`（連測試都沒用） | 誤報 | pydantic `model_config` 由框架讀取 |
| `berth/logs.py:122` | attribute `msg`（連測試都沒用） | 誤報 | 對 `LogRecord.msg` 賦值，框架屬性 |
| `berth/pipeline/planning.py:34` | variable `Waiter`（連測試都沒用） | 真的沒人用 | 型別別名全 repo 零引用，見 C6 |
| `berth/adapters/ai.py:23` | class `AiPlanner`（只有測試用） | 刻意保留 | M5 AI 任務核心的介面，`docs/plan.md:322` 寫明「至今沒有呼叫端」；`tests/unit/test_ai.py` 守著 |
| `berth/adapters/ai.py:26` | method `propose`（只有測試用） | 刻意保留 | M5 AI 任務核心的介面，`docs/plan.md:322` 寫明「至今沒有呼叫端」；`tests/unit/test_ai.py` 守著 |
| `berth/adapters/ai.py:27` | variable `rules_plan`（只有測試用） | 刻意保留 | M5 AI 任務核心的介面，`docs/plan.md:322` 寫明「至今沒有呼叫端」；`tests/unit/test_ai.py` 守著 |
| `berth/adapters/ai.py:40` | class `NullAiPlanner`（只有測試用） | 刻意保留 | M5 AI 任務核心的介面，`docs/plan.md:322` 寫明「至今沒有呼叫端」；`tests/unit/test_ai.py` 守著 |
| `berth/adapters/ai.py:47` | method `propose`（只有測試用） | 刻意保留 | M5 AI 任務核心的介面，`docs/plan.md:322` 寫明「至今沒有呼叫端」；`tests/unit/test_ai.py` 守著 |
| `berth/adapters/ai.py:48` | variable `rules_plan`（只有測試用） | 刻意保留 | M5 AI 任務核心的介面，`docs/plan.md:322` 寫明「至今沒有呼叫端」；`tests/unit/test_ai.py` 守著 |
| `berth/adapters/indexer/__init__.py:56` | variable `leechers`（只有測試用） | 真的沒人用 | `IndexerResult.leechers` 只有 adapter 填、測試斷言，產品碼沒讀，見 C9 |
| `berth/adapters/indexer/fake.py:14` | class `FakeIndexerSearch`（只有測試用） | 誤報 | fake 測試接縫：tests/integration/arrange.py 等 87 處用 |
| `berth/adapters/indexer/fake.py:40` | attribute `closed`（只有測試用） | 真的沒人用 | `FakeIndexerSearch.closed` 沒有任何斷言讀它，見 C9 |
| `berth/adapters/indexer/fake.py:65` | attribute `closed`（只有測試用） | 真的沒人用 | `FakeIndexerSearch.closed` 沒有任何斷言讀它，見 C9 |
| `berth/adapters/jellyfin/fake.py:126` | variable `LIBRARY_SCAN_TASK`（只有測試用） | 誤報 | fake 測試接縫：`test_resolver.py`、`test_issue_repairs.py` import |
| `berth/adapters/jellyfin/fake.py:131` | class `FakeJellyfinClient`（只有測試用） | 誤報 | fake 測試接縫：測試與 dev 替身（239 處） |
| `berth/adapters/jellyfin/fake.py:310` | method `revoke_api_key`（只有測試用） | 誤報 | fake 測試接縫：`tests/integration/test_setup_choice.py:963` 呼叫 |
| `berth/adapters/prowlarr/fake.py:161` | class `FakeProwlarrClient`（只有測試用） | 誤報 | fake 測試接縫：測試與 dev 替身 |
| `berth/adapters/prowlarr/fake.py:292` | method `signs_in`（只有測試用） | 誤報 | fake 測試接縫：`tests/integration/test_setup_api.py:972` 起呼叫 |
| `berth/adapters/qbittorrent/fake.py:122` | attribute `calls`（只有測試用） | 誤報 | fake 測試接縫：`test_health_service.py:101`、`test_setup_choice.py:106`、`test_discover.py:366` 斷言 |
| `berth/adapters/qbittorrent/fake.py:270` | attribute `syncs`（只有測試用） | 誤報 | fake 測試接縫：`test_qbit_poller.py:205` 斷言 |
| `berth/adapters/qbittorrent/fake.py:45` | class `FakeQbittorrentClient`（只有測試用） | 誤報 | fake 測試接縫：測試與 dev 替身 |
| `berth/adapters/qbittorrent/fake.py:74` | attribute `calls`（只有測試用） | 誤報 | fake 測試接縫：`test_health_service.py:101`、`test_setup_choice.py:106`、`test_discover.py:366` 斷言 |
| `berth/adapters/qbittorrent/fake.py:99` | attribute `syncs`（只有測試用） | 誤報 | fake 測試接縫：`test_qbit_poller.py:205` 斷言 |
| `berth/adapters/rss/fake.py:8` | class `FakeFeedFetcher`（只有測試用） | 誤報 | fake 測試接縫：測試與 dev 替身 |
| `berth/adapters/tmdb/fake.py:20` | class `FakeTmdbClient`（只有測試用） | 誤報 | fake 測試接縫：測試與 dev 替身 |
| `berth/adapters/tmdb/fake.py:51` | attribute `calls`（只有測試用） | 誤報 | fake 測試接縫：`test_health_service.py:101`、`test_setup_choice.py:106`、`test_discover.py:366` 斷言 |
| `berth/adapters/tmdb/fake.py:83` | attribute `calls`（只有測試用） | 誤報 | fake 測試接縫：`test_health_service.py:101`、`test_setup_choice.py:106`、`test_discover.py:366` 斷言 |
| `berth/adapters/torrent_fake.py:15` | class `FakeTorrentFetcher`（只有測試用） | 誤報 | fake 測試接縫：測試與 dev 替身 |
| `berth/api/health.py:37` | variable `setup_completed`（只有測試用） | 誤報 | pydantic 回應欄位，routes.tsx:74 路由守衛讀 |
| `berth/api/health.py:97` | variable `window_seconds`（只有測試用） | 真的沒人用 | `BudgetOut.window_seconds` 前端 BudgetCard 只解構 `limit`、`sites`，見 C4 |
| `berth/api/jobs.py:183` | variable `media_title`（只有測試用） | 誤報 | pydantic 回應欄位，jobs/jobState.ts:73 等讀 |
| `berth/api/jobs.py:185` | variable `media_title_en`（只有測試用） | 誤報 | pydantic 回應欄位，jobs/jobState.ts:73 等讀 |
| `berth/api/jobs.py:187` | variable `route_name`（只有測試用） | 誤報 | pydantic 回應欄位，JobFacts / seriesByWork / AddRoute 讀 |
| `berth/api/jobs.py:188` | variable `route_slug`（只有測試用） | 真的沒人用 | `JobOut.route_slug` 前端沒讀，見 C4 |
| `berth/api/jobs.py:224` | variable `attention`（只有測試用） | 誤報 | pydantic 回應欄位，`counts[option]` 動態取（JobsPage.tsx:114） |
| `berth/api/jobs.py:228` | variable `open`（只有測試用） | 誤報 | pydantic 回應欄位，`counts[option]`（DownloadsPanel.tsx:77） |
| `berth/api/jobs.py:283` | variable `links_missing`（只有測試用） | 誤報 | pydantic 回應欄位，JobDelete.tsx:194 讀 |
| `berth/api/jobs.py:287` | variable `sources_missing`（只有測試用） | 誤報 | pydantic 回應欄位，JobDelete.tsx:194 讀 |
| `berth/api/jobs.py:288` | variable `source_bytes`（只有測試用） | 真的沒人用 | 同上，見 C4 |
| `berth/api/plans.py:143` | variable `applied`（只有測試用） | 誤報 | pydantic 回應欄位，PlanEditor.tsx:141,256 讀 |
| `berth/api/review.py:122` | variable `ref`（只有測試用） | 誤報 | pydantic 回應欄位，AuditRow / AuditGroup / InventoryPage 讀 `row.ref` |
| `berth/api/review.py:159` | variable `ref`（只有測試用） | 誤報 | pydantic 回應欄位，AuditRow / AuditGroup / InventoryPage 讀 `row.ref` |
| `berth/api/review.py:198` | variable `ref`（只有測試用） | 誤報 | pydantic 回應欄位，AuditRow / AuditGroup / InventoryPage 讀 `row.ref` |
| `berth/api/review.py:230` | variable `ref`（只有測試用） | 誤報 | pydantic 回應欄位，AuditRow / AuditGroup / InventoryPage 讀 `row.ref` |
| `berth/api/routes.py:107` | variable `route_name`（只有測試用） | 誤報 | pydantic 回應欄位，JobFacts / seriesByWork / AddRoute 讀 |
| `berth/api/routes.py:122` | variable `uses_tvdb`（只有測試用） | 誤報 | pydantic 回應欄位，AddRoute.tsx:188 / RouteStep.tsx:753 讀 |
| `berth/api/rss.py:118` | variable `exclusions`（只有測試用） | 誤報 | pydantic 回應欄位，FeedSection.tsx:256、SeriesSection.tsx:251 讀 |
| `berth/api/rss.py:213` | variable `media_title`（只有測試用） | 誤報 | pydantic 回應欄位，jobs/jobState.ts:73 等讀 |
| `berth/api/rss.py:214` | variable `media_title_en`（只有測試用） | 誤報 | pydantic 回應欄位，jobs/jobState.ts:73 等讀 |
| `berth/api/rss.py:216` | variable `route_name`（只有測試用） | 誤報 | pydantic 回應欄位，JobFacts / seriesByWork / AddRoute 讀 |
| `berth/api/rss.py:227` | variable `exclusions`（只有測試用） | 誤報 | pydantic 回應欄位，FeedSection.tsx:256、SeriesSection.tsx:251 讀 |
| `berth/api/rss.py:235` | variable `latest_title`（只有測試用） | 誤報 | pydantic 回應欄位，SeriesSection / SubscribePanel 讀 |
| `berth/api/rss.py:236` | variable `latest_at`（只有測試用） | 誤報 | pydantic 回應欄位，SeriesSection / SubscribePanel 讀 |
| `berth/api/rss.py:238` | variable `latest_episode`（只有測試用） | 誤報 | pydantic 回應欄位，SeriesSection.tsx:272 讀 |
| `berth/api/rss.py:582` | variable `bound_to`（只有測試用） | 誤報 | pydantic 回應欄位，SubscribePanel.tsx:329 讀 |
| `berth/api/schemas.py:114` | variable `blocked`（只有測試用） | 誤報 | pydantic 回應欄位，SetupPage.tsx:857 讀 |
| `berth/api/schemas.py:118` | variable `web_ui_login`（只有測試用） | 誤報 | pydantic 回應欄位，QbittorrentStep 等讀 |
| `berth/api/schemas.py:122` | variable `web_ui_login_by_berth`（只有測試用） | 誤報 | pydantic 回應欄位，setup/ServiceDoors.tsx 讀 |
| `berth/api/schemas.py:296` | variable `unplayed_episodes`（只有測試用） | 誤報 | pydantic 回應欄位，components/watchLine.ts 讀 |
| `berth/api/schemas.py:351` | variable `basis`（只有測試用） | 誤報 | pydantic 回應欄位，rss/firstBatchAsk.ts:26 讀 |
| `berth/api/schemas.py:75` | variable `probe_carried`（只有測試用） | 誤報 | pydantic 回應欄位，RouteCheckList.tsx:67 讀 |
| `berth/api/search.py:152` | variable `next_seasons`（只有測試用） | 誤報 | pydantic 回應欄位，SearchPanel.tsx:457 讀 |
| `berth/api/setup.py:126` | variable `waited_seconds`（只有測試用） | 誤報 | pydantic 回應欄位，JellyfinConnection.tsx:103 讀 |
| `berth/api/setup.py:144` | variable `current_step`（只有測試用） | 誤報 | pydantic 回應欄位，SetupPage.tsx 多處讀 |
| `berth/api/setup.py:148` | variable `owner_signs_in`（只有測試用） | 誤報 | pydantic 回應欄位，OwnerStep.tsx 讀 |
| `berth/api/setup.py:150` | variable `jellyfin_startup`（只有測試用） | 誤報 | pydantic 回應欄位，setup/OwnerStep.tsx 讀 |
| `berth/api/setup.py:154` | variable `window_seconds`（只有測試用） | 誤報 | pydantic 回應欄位，JellyfinConnection.tsx:104 / ServiceChoice.tsx:836 讀（SetupStatusOut 那份） |
| `berth/api/setup.py:461` | variable `uses_tvdb`（只有測試用） | 真的沒人用 | `LibraryOut.uses_tvdb`；前端只讀 `LibraryChoiceOut` / `LibraryOptionOut` 的同名欄位，見 C2 |
| `berth/api/setup.py:463` | variable `has_berth_path`（只有測試用） | 真的沒人用 | `LibraryOut.has_berth_path`；前端讀的是 `LibraryChoiceOut` 那份，見 C2 |
| `berth/api/setup.py:496` | variable `api_key_present`（只有測試用） | 誤報 | pydantic 回應欄位，前端 BerthBoard / IndexerStep / JellyfinExisting / TmdbStep 讀 |
| `berth/api/setup.py:506` | variable `bundled_default`（只有測試用） | 誤報 | pydantic 回應欄位，setup/autoDock.ts:15 讀 |
| `berth/api/setup.py:696` | variable `removable`（只有測試用） | 誤報 | pydantic 回應欄位，setup/IndexerSites.tsx:98 讀 |
| `berth/api/setup.py:732` | variable `api_key_present`（只有測試用） | 誤報 | pydantic 回應欄位，前端 BerthBoard / IndexerStep / JellyfinExisting / TmdbStep 讀 |
| `berth/api/setup.py:743` | variable `web_ui_login`（只有測試用） | 誤報 | pydantic 回應欄位，QbittorrentStep 等讀 |
| `berth/api/setup.py:747` | variable `web_ui_login_by_berth`（只有測試用） | 誤報 | pydantic 回應欄位，setup/ServiceDoors.tsx 讀 |
| `berth/api/setup.py:920` | variable `api_key_present`（只有測試用） | 誤報 | pydantic 回應欄位，前端 BerthBoard / IndexerStep / JellyfinExisting / TmdbStep 讀 |
| `berth/api/setup.py:956` | variable `has_berth_path`（只有測試用） | 誤報 | pydantic 回應欄位，RouteStep.tsx:441,800 讀（LibraryChoiceOut 那份） |
| `berth/api/setup.py:957` | variable `uses_tvdb`（只有測試用） | 誤報 | pydantic 回應欄位，AddRoute.tsx:188 / RouteStep.tsx:753 讀 |
| `berth/api/setup.py:961` | variable `has_route`（只有測試用） | 誤報 | pydantic 回應欄位，setup/RouteStep.tsx:164 讀 |
