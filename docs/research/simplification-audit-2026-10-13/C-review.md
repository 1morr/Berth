# C 複核

複核範圍：`C_report.md` 的 C1–C10、文件偏差、刻意保留區、工具判定表。所有證據是複核者在 `t86` 工作樹（HEAD `c5d4060`）重新 grep 或讀檔得到的，沒有沿用 worker 的證據。

| 編號 | 判定（通過 / 駁回 / 改判刻意保留 / 通過但修正） | 理由（附你自己查到的證據） | 修正後的建議 / 大小 / 風險（若有改） |
|---|---|---|---|
| C1 | 通過 | 兩支端點的實作完全相同，都是 `return health_detail(await read_health(session))`，回 `HealthDetailOut`（`berth/api/settings.py:45-48`、`berth/api/health.py:53-56`）。後端自己的註解（settings.py:47「與健康頁同一份形狀——同一件事不該有兩種說法」）和前端註解（`web/src/api/health.ts:11`「設定頁的 `GET /api/settings/services` 回的是同一份」）都承認是同一份資料。前端兩邊需要的形狀也一樣：`HealthSection.tsx:17-18` 只從 `services` 取一列，`HealthPage.tsx:36-39` 用的是 `healthDetailQueryOptions` 加上 `refetchInterval`，資料形狀相同。分成兩把 key 已經造成實際的同步負擔：`useServiceCheck.ts:20-21` 每次都要寫兩把；`recheckRoutes.ts:16` 作廢 `['health']`，會連帶作廢 `['health','detail']`，但碰不到 `['settings','services']`，兩份快取在這條路徑上已經會不一致。門禁的差別（前者 admin、後者 SIGNED_IN，`tests/integration/test_auth_api.py:446,489`）不影響這件事，因為設定頁本來就只有 admin 進得去，而 admin 也讀得到 `/health/detail`。查過 progress.md 的「偏差與決定」（第 224 行起），沒有「要分成兩支」的決定：第 460 行只記新增端點，CHANGELOG.md:1588 只寫「`GET /api/settings/services` 照舊（設定頁的健康卡讀它）」，記的是現況，沒有給理由。 | 建議不變。大小要修正：前端測試另有 4 個檔用 `'GET /api/settings/services'` 打樁（`IndexerSettingsPage.test.tsx:58`、`JellyfinSettingsPage.test.tsx:22`、`QbittorrentSettingsPage.test.tsx:13`、`RouteRecheck.test.tsx:228`），後端還有 `test_auth_api.py:446` 的門禁表那一列和 `test_health_api.py:194-242`；另外要同步 `CHANGELOG.md`、`docs/plan.md:391`。整體仍是「小」。風險：刪掉一支 GET，消費者只有自家前端；不碰持久化資料。 |
| C2 | 通過但修正 | 欄位確實沒人讀。`web/src` 裡 `JellyfinSetup` 的消費點（`SetupPage.tsx`、`autoDock.ts`、`RouteStep.tsx`、`jellyfinSteps.ts`）都不讀 `.libraries`；`RouteStep.tsx:163` 的 `setup.libraries` 裡，`setup` 是 `RouteSetup`（`common.setup`），不是 JellyfinSetup。`metadata_fetchers` 在前端只出現在 `web/src/test/fixtures.ts:119`。worker 漏了一點：移除 API 欄位之後，services 那一側也會跟著失去唯一的消費者，包括 `berth/services/jellyfin.py:185` 的 `LibraryView`、`:205` 的 `JellyfinSetupView.libraries`、`:1107` 的 `_library_view`。另外，`_library_view` 和 `services/routes.py:1369` 的 `_library_choice` 各自算了一次 `berth_path`、`has_berth_path`、`uses_tvdb`（`jellyfin.py:1114` 與 `routes.py:1380` 是同一句 `any(TVDB_MARKER in …)`），等於同一個判斷寫了兩處。 | 建議：拿掉 `JellyfinSetupOut.libraries` 和 `LibraryOut`，連同 services 的 `LibraryView`、`_library_view`、`JellyfinSetupView.libraries` 一起刪；`setup.jellyfin.libraries` 這份資料庫快照照留。要改寫的測試：`tests/integration/test_setup_api.py:629,692-694`；`tests/integration/test_setup_jellyfin.py:290-308` 守的是「套件內路徑與 Berth 路徑同一支函式算」，改成斷言 `RouteSetup` 的 `LibraryChoice.berth_path`，或直接測 `berth_path()`。大小從「小」改為「小～中」。風險：API 回應形狀會變（需重跑 `gen:api`、改 fixtures）；不碰持久化資料。 |
| C3 | 通過但修正 | 前端 `web/src` 裡用 `-w completed` 搜，非測試的讀取點只有 `routes.tsx:74` 的 `health.setup_completed`。`SetupPage.tsx:386-396` 呼叫 `finish` 之後，只把 `/health` 那一份快取的 `setup_completed` 改成 true，沒有讀 `SetupStatusOut.completed`；`RouteSetupOut.completed`（`berth/api/setup.py:977`）前端也沒讀。worker 有一處說錯：它說「services 內部的 `SetupStatus.completed` 仍用得上」，但 `berth` 裡用 `.completed` 搜，services 的 `SetupStatus.completed`（`services/setup.py:144,1095`）和 `RouteSetup.completed`（`services/routes.py:197,226`）只被 API 的 `from_attributes` 和測試讀（`tests/integration/test_setup_owner.py:97`、`test_setup_routes.py:1279`）。資料庫裡的 `SetupSettings.completed` 才是真正有人讀的那一個（`is_setup_complete`）。 | 建議：拿掉兩個 API 欄位，連同 services 那兩個 view 欄位一起刪。要改的測試斷言：`test_setup_api.py:98,1275`、`test_settings_take_over.py:118`、`test_setup_owned_writes.py:571`、`test_setup_owner.py:97`、`test_setup_routes.py:1279`。大小仍是「小」。風險：API 回應形狀會變；`POST /setup/complete` 的回應少一個欄位，但前端沒讀。 |
| C4 | 通過但修正 | 逐欄搜 `web/src` 與 `web/e2e`（排除 `schema.d.ts`、測試、i18n），以下欄位的讀取點都是 0：`link_bytes`、`source_bytes`、`route_slug`、`trigger_ref`、`user_id`、`content_path`、`completed_at`、`imported_at`、`engine`、`engine_version`、`frees_at`、`seen_at`、`file_kind`。`window_seconds` 的 3 處都是 `SetupStatusOut` 那一份（`JellyfinConnection.tsx:104`、`ServiceChoice.tsx:836`），`BudgetCard.tsx:22` 只解構 `{ limit, sites }`。`since` 只出現在英文文案裡。`premiere` 只出現在綁定理由的 i18n 參數裡，那是後端 `params` 帶來的，不是 `BangumiOut.premiere`。文件方面，brief、plan、progress 都沒有寫「這些 API 欄位要留給 M5 或除錯用」：`plan.md:127,131` 只定義 `jobs` 與 `plans` 的資料庫欄位，`plan.md:322`（§4.5）談的是 AiPlanner，沒有提到 `PlanOut.engine`，所以不改判刻意保留。worker 漏掉的消費點有四處：(1) `content_path` 被真實服務的 e2e 讀（`tests/e2e/test_1_m1_pipeline.py:98,126`、`tests/e2e/test_3_m2_repair.py:159` 靠它找 complete 裡的檔案）；(2) 後端有 API 斷言 `test_jobs_api.py:310`（`route_slug`）、`test_plans_api.py:276`（`engine`）、`test_health_api.py:342`（`window_seconds`）；(3) `plan.md:402` 把 `GET /rss/mikan/bangumi/{id}` 的回應寫成 `{id, title, premiere, subgroups}`；(4) `plan.md:404` 的 budget 描述也要同步。 | 建議大致不變，但要拆開處理：`content_path` 只有測試在用，可是刪了 e2e 就要改成用 `save_path` 加 `name` 自己組路徑，風險從「無」升到「中」，建議另列或維持現狀。`engine` / `engine_version` 與 M5「AI 提案還是規則提案」可能有關，這條判斷沒有文件依據，維持「需使用者決定」。刪 `premiere` 要同輪改 `plan.md:402`。大小仍是「中」。風險：API 回應形狀會變（只有自家前端消費），加上一處 e2e。 |
| C5 | 通過 | `berth/adapters/qbittorrent/__init__.py:587-595` 的 `_parse` 和 `berth/adapters/versions.py:8-17` 的 `parse_version` 做的是同一件事。`_parse` 只有 `:81,86,94` 三處呼叫。兩者在邊界上有差：`_parse` 會 strip、取片段裡的所有數字、遇到無數字的片段就停；`parse_version` 不 strip、只取開頭的數字、無數字的片段記成 0。不過 webapi 版本字串來自 `client.py:97`，那裡已經 `.strip()` 過，格式也一定是 `2.x.y`；兩者遇到無法解析的輸入都會小於 `MIN_WEBAPI`，所以實際行為相同。progress.md:155（M4 票 17）只記「抽成 `adapters/versions.parse_version`（Jellyfin 共用）」，沒有說 qBittorrent 為什麼要另外一份。 | 不變。驗收時跑 `tests/unit/test_adapters.py:339-359` 的參數化版本閘門。 |
| C6 | 通過但修正 | `Waiter` 已確認：`berth/pipeline/planning.py:34` 是唯一出現的地方，`berth`、`tests`、`scripts` 都沒有引用。`Sleeper` / `Clock` 的別名在 `pipeline/{downloads,health,reconciling,rss}.py` 各定義一次，`adapters/budget.py:30` 有 `Clock`，`services/indexer.py:92` 有 `Sleeper`，都已確認。迴圈骨架那部分要降級：七個 `run()` 確實長得一樣（while、`whole_tick`、`except Exception`、`logger.exception`），但會改變答案的判斷已經收在一處了，分別是 `is_setup_complete` 和 `pipeline/ticks.whole_tick`。重複的只是約 8 行的 try/except/log，比較接近寫法風格，不是同一個判斷寫兩處。 | 建議：刪 `Waiter`，把 pipeline 裡 4 份 `Sleeper` / `Clock` 收到 `pipeline/ticks.py`。`adapters/budget.py` 和 `services/indexer.py` 的那幾份不能從 `pipeline` import（依賴方向是 `pipeline → services → adapters`，由 import-linter 強制），要嘛留著，要嘛放到更低層，例如 `berth/domain`，這是設計決定。迴圈骨架那一項建議從發現移除，或標成「風格、可不做」。大小：小。風險：無。 |
| C7 | 通過但修正 | 操作者判斷的部分成立，但次數要更正：`actor_of(user.id if user is not None else None)` 內聯的地方是 10 處，不是約 12 處（`files.py:153` 1 處、`issues.py:242,261` 2 處、`jobs.py:442,516` 2 處、`review.py:334,351,365,380,404` 5 處），另外 `plans.py:298` 有一個 `_actor`。worker 寫的 `jobs.py:345` 是 `current_user`，不是 `actor_of`。「沒登入的人算 system」這個決定確實寫了 11 遍。`JellyfinWebOut.model_validate(await jellyfin_web(...))` 那部分（`inventory.py:228`、`jellyfin.py:186`、`media.py:316`、`settings.py:68`）只是同一支 service 的單行包裝，沒有任何判斷可以分岔，屬於樣板寫法，不算兩套做法。 | 建議：只做 actor 那一半，把 `plans._actor` 移到 `api/gate.py` 共用。`JellyfinWebOut` 那一項從發現移除。大小：小。風險：無。 |
| C8 | 通過但修正 | 已確認：`berth` 裡沒有任何地方讀 `Config.data_root`。`services/setup.py:763` 的 `_data_root` 讀的是 `PathSettings`。產品路徑寫死在 `PathSettings` 的預設值，`plan.md:591` 也寫明「incomplete / complete 根目錄固定在 `/data/torrent/…`」。讀它的只有 `tests/unit/test_config.py:24,58,99` 和 `scripts/fake_setup_server.py:2029`。後者在 `:1883` 自己把 `DATA_ROOT` 設成 `config_root / "data"` 再讀回來，可以直接用那個值。worker 漏了文件偏差：`docs/development.md:46` 的環境變數表寫 `DATA_ROOT` 是「媒體根：incomplete、complete 與媒體庫路徑都在它底下」，暗示 Berth 程序會讀它；`plan.md:30` 也把它列成 Berth 的路徑常數。另外 `scripts/experiments/*.py` 和 `tests/conftest.py:22`、`tests/unit/test_cli.py:214` 會傳 `DATA_ROOT` 給 `load_config`，欄位移除後這些值只是被忽略，不會壞。 | 建議：除了 worker 列的項目，同輪還要改 `docs/development.md:46`（明講 `DATA_ROOT` 只給 compose 掛載用，不是 Berth 程序的變數）、`plan.md:30`、`deploy/Dockerfile:46`、CHANGELOG。大小：小。風險：設定項變動，但行為不變，因為現況本來就沒有作用。 |
| C9 | 通過但修正 | 已確認 `IndexerResult.leechers` 沒有產品讀者：`berth` 裡只有 `adapters/indexer/__init__.py:56` 定義、`prowlarr.py:94` 填值。`FakeIndexerSearch.closed` 在 `fake.py:40,65` 只有寫入；`tests`、`scripts` 用 `\.closed` 搜都是 0 筆，而且其他 fake 沒有同名屬性。worker 低估了改動範圍：建構時傳 `leechers=` 的還有 `tests/integration/test_search_api.py:56,70,82,90`、`scripts/fake_setup_server.py:714,725`。 | 建議不變，改動清單加上這 6 處。大小：小。風險：無。 |
| C10 | 改判刻意保留 | worker 的理由是「『不存在』已由 `test_openapi_contract` 與門禁表的雙向檢查涵蓋」，這個說法不成立。`tests/integration/test_auth_api.py:564-566` 只要求「app 上的路由和 ACCESS 表一致」，如果有人把 `/media/{id}/track` 或 `/setup/tmdb/skip` 加回來，只要在 ACCESS 表加一列就會綠燈；`test_openapi_contract.py` 守的是拒絕 enum 和 schema，不管路由存不存在。所以這兩條測試是兩個產品決定唯一的閘門，而且決定寫在 docstring 裡：`test_media_api.py:128-129`「『追蹤』不是一個動作（票 04b）：`tracked` 是推導出來的」；`test_setup_api.py:1057`「TMDB 那一半根本沒有這一支（票 02b）」。後端也有對應註解：`berth/api/setup.py:941`「**沒有 `/tmdb/skip`**：這一步是閘門，測不過就走不到第 8 步（票 02b）」。它們守的是「這個介面不能存在」這個仍然有效的決定，不是守一個已經消失的介面。 | 移到「刻意保留」，出處為 `tests/integration/test_media_api.py:128-129`、`tests/integration/test_setup_api.py:1057,1067`、`berth/api/setup.py:941`。 |

## 文件偏差

- **`docs/plan.md:52` 的 `berth reconcile`：確認是文件偏差。** `berth/cli.py:44-87` 的子指令只有 `serve`、`openapi`、`bench`、`rebuild-ledger`。`git log -S"reconcile" -- berth/cli.py` 查無結果，表示這個子指令從來沒有實作過，不是後來被拿掉的。手動觸發對帳的入口是 API `POST /api/issues/reconcile`（`berth/api/issues.py:268`）。同一行也漏列了 `serve` 和 `openapi`。這屬於「文件描述了不存在的介面」。
- **`docs/development.md:46`（以及 `docs/plan.md:30`）的 `DATA_ROOT`（複核者新增，見 C8）：** 文件把它寫成 Berth 程序讀的媒體根，但 `Config.data_root` 沒有產品讀者。實際上它只在 compose 那一層把宿主路徑掛成 `/data` 時有作用。

## 刻意保留抽查

| 項目 | 出處核對 | 結果 |
|---|---|---|
| `adapters/ai.py` 的 `AiPlanner` / `NullAiPlanner` | `docs/plan.md:322` 原文寫「介面在 M1 就定好…**至今沒有呼叫端**…是 M5 的 AI 任務『規則層 low 的 Plan』的核心」 | 成立 |
| 各 router 的 `XRefusalOut` 加 `_STATUS` 樣板 | `docs/progress.md:84` 是 session 紀錄那一列，不在「偏差與決定」段；內容記載新閘門 `test_openapi_contract.py` 會掃出每一個 `*Refusal` enum，封閉集合與 model 都要進 OpenAPI。`berth/api/files.py:194-200` 有註解：「命名照 `review_refusal`（`test_openapi_contract.py` 的登記簿以函式名為鍵）」 | 成立，但出處應補上「程式註解 `files.py:195-196`」，因為 progress.md:84 不在偏差段 |
| `review.py` 的 4 個 `*ReasonOut` | 同上，每個用自己的 enum 當 `code` | 成立 |
| `GET /jellyfin/libraries` 與 `POST /setup/routes/libraries` | `docs/progress.md:871`（偏差段）：「新增 Route 的媒體庫與路徑向 Jellyfin 現查…不讀第 3 步的快照」 | 成立 |
| `berth rebuild-ledger` 與 `POST /issues/rebuild-ledger` | `docs/plan.md:866` 寫「M4 票 60 起畫面上也按得到」；`docs/progress.md:203` 有 `POST /issues/rebuild-ledger` 的記載 | 成立 |
| 三條 confirm 端點 | `berth/api/review.py:343-349` 的 docstring：批次版「已經被別處確認或撤銷的列跳過…不是 409」 | 成立，語意確實不同 |
| `/settings/services/{kind}/test` 與 `/setup/services/{kind}/test` 與 `/health/check` | `web/src/api/settings.ts:8-14` 的註解，以及 `docs/progress.md:118` | 成立 |

## 工具判定抽查

判成「誤報」的條目抽了 20 條，全部成立：

| 條目 | 複核證據 |
|---|---|
| `http.py:125,127` 的 `exc_type`、`tb` | `berth/adapters/http.py:121-127` 是 `__aexit__` 的協定簽章 |
| `mikan.py:143,205,213,220,262,275,331,351,355` 的 `handle_*` | 所屬類別 `_RssLink`、`_BangumiTitle`、`_BangumiHits`、`_Subgroups` 都繼承 `HTMLParser`（`mikan.py:136,196,256,318`） |
| `events.py:64` 的 `media_type` | `events.py:58-64` 的註解說明 FastAPI 讀它來決定 content type |
| `logs.py:122` 的 `msg` | 對 `LogRecord.msg` 賦值（`logs.py:121-122`） |
| `inventory.py:80` 的 `has_imports` | `web/src/auth/destination.ts:44` 有讀 |
| `jobs.py:191` 的 `user_name` | `web/src/pages/JobDetailPage.tsx:99` 有讀 |
| `jobs.py:204` 的 `retryable` | `web/src/jobs/JobActions.tsx:47` 有讀 |
| `review.py:297` 的 `issues_open` | `web/src/pages/ReviewPage.tsx:121,124` 有讀 |
| `rss.py:126` 的 `ever_read` | `web/src/rss/FirstRoundSection.tsx:91` 有讀 |
| `schemas.py:193,206` 的 `interval_seconds` | `PollerCard.tsx:41`、`HealthPage.tsx:83` 有讀 |
| `schemas.py:314` 的 `still_url` | `media/WatchArea.tsx:281` 有讀 |
| `setup.py:269` 的 `resolvable` | `api/setup.ts:56` 有讀 |
| `schemas.py:130`、`setup.py:753` 的 `web_port` | `setup/serviceWeb.ts:23` 有讀 |
| `setup.py:506` 的 `bundled_default` | `setup/autoDock.ts:15` 有讀 |
| `setup.py:696` 的 `removable` | `setup/IndexerSites.tsx:98` 有讀 |
| `setup.py:961` 的 `has_route` | `setup/RouteStep.tsx:164` 有讀 |
| `search.py:152` 的 `next_seasons` | `media/SearchPanel.tsx:457` 有讀（worker 寫成 `search/SearchPanel.tsx`，路徑小錯，結論不變） |
| `schemas.py:351` 的 `basis` | `rss/firstBatchAsk.ts:26` 有讀 |
| `setup.py:126` 的 `waited_seconds` | `JellyfinConnection.tsx:103` 有讀 |
| `plans.py:143` 的 `applied`、`jobs.py:283` 的 `links_missing`、`schemas.py:75` 的 `probe_carried`、`schemas.py:296` 的 `unplayed_episodes` | 分別在 `plans/PlanEditor.tsx:141`（worker 寫成 `PlanEditor.tsx` 在 pages 底下，實際在 plans 底下）、`JobDelete.tsx:194`、`RouteCheckList.tsx:67`、`watchLine.ts:14` 有讀 |
| fake 接縫：`LIBRARY_SCAN_TASK`、`revoke_api_key`、`signs_in`、qBittorrent 的 `calls` / `syncs` | `test_issue_repairs.py:23,384`；其餘由測試呼叫或斷言 |
| `tmdb/fake.py:51,83` 的 `calls` | 結論成立，但 worker 給的證據是 qBittorrent 的那幾行（`test_health_service.py:101` 等），引錯了。實際讀 `FakeTmdbClient.calls` 的是 `tests/integration/test_discover.py:366` 與 `test_setup_source.py:473` |

判成「真的沒人用」的條目全部核對，全部成立：

| 條目 | 複核證據 |
|---|---|
| `jobs.py:284` 的 `link_bytes`、`jobs.py:288` 的 `source_bytes` | 前端讀取點是 0；後端也沒有測試用 `["link_bytes"]` 或 `["source_bytes"]` 斷言 |
| `planning.py:34` 的 `Waiter` | 全 repo 只有定義 |
| `indexer/__init__.py:56` 的 `leechers` | 產品沒有讀者，只有 `test_indexer_search.py:44` 斷言 |
| `indexer/fake.py:40,65` 的 `closed` | 有寫入，沒有讀取 |
| `health.py:97` 的 `window_seconds` | `BudgetCard.tsx:22` 只解構 `{ limit, sites }` |
| `jobs.py:188` 的 `route_slug` | 前端讀取點是 0，只有 `test_jobs_api.py:310` 斷言 |
| `setup.py:461` 的 `uses_tvdb`、`setup.py:463` 的 `has_berth_path` | 屬於 `LibraryOut`，見 C2 |

## 複核者另外發現（若有，需附證據）

- **`uses_tvdb`、`berth_path`、`has_berth_path` 在 services 裡算了兩次（與 C2 相連，屬跨區）。** `berth/services/jellyfin.py:1107-1117` 的 `_library_view` 和 `berth/services/routes.py:1369-1387` 的 `_library_choice` 各組一次同樣的三格，其中 `uses_tvdb=any(TVDB_MARKER in name.lower() for name in library.metadata_fetchers)` 一字不差地出現在 `jellyfin.py:1114` 與 `routes.py:1380`。照 C2 的建議刪掉 `_library_view` 之後，重複就消失了；如果 C2 不做，這一條就該單獨列為「同一判斷寫兩處」。
- **C2、C3 的 services view 欄位會跟著變成沒人讀**（`JellyfinSetupView.libraries`、`SetupStatus.completed`、`RouteSetup.completed`）。這幾個欄位屬於 services 區，應該通知審 services 的 worker 或 synthesize 步驟合併處理，避免兩邊各自列一條、或互相以為對方會刪。
