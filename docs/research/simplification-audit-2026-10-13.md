# 簡化審計（2026-10-13，票 86）

> 只審不改。範圍是 main `c5d4060`（票 83、84 合併之後）。只找兩類：**同一件事兩套做法**、**沒人用的東西**。使用者挑中的項目由協調者另外開票。

## 怎麼做的

1. 先跑工具：vulture 掃 Python、knip 掃 `web/`，原始輸出和逐條判定見〈附錄 A〉。
2. 分四區各派一個 sonnet worker 找重複和死碼：services、parser/naming/domain/models/db、adapters/api/pipeline 與頂層、`web/src`。每個 worker 都要逐條判定自己那一區的工具結果。
3. 每區的報告再交給一個 opus 複核者，獨立重新 grep、讀兩邊程式碼，逐條判定通過、駁回或改判刻意保留，並抽查刻意保留的出處和工具判定。**下面只列通過複核的項目**，修正過的建議以複核者的版本為準。駁回的列在〈複核駁回〉，方便日後不必再查一次。
4. 兩區撞到同一件事時合併成一條（例如設定頁與健康頁的兩支端點、只寫不讀的資料庫欄位）。

原始報告與複核在 [`simplification-audit-2026-10-13/`](simplification-audit-2026-10-13/)：`X-worker.md` 是 worker 的版本，`X-review.md` 是複核者的版本。兩份衝突時以 review 為準。

全盤印象：沒有整個模組或整條 API 端點沒人用（114 條路由都有前端消費者；`berth/services` 定義檔以外零引用的頂層符號只有 `commands.mark_of`，而它是測試接縫）；i18n 2085 個 key 也沒有找到未使用的。發現集中在「同一個判斷寫了兩三份」和「欄位只寫不讀」。

## 清單（依值不值得改排序）

排序原則：兩份**已經長出不同答案**的排最前面；接著是註解自稱單一來源、實際卻有兩份的；再來是便宜、確定、零風險的；需要先拍板設計或資料格式的放最後。

大小：小 = 一個 session 內、一兩個檔；中 = 一個 session、多檔；大 = 要拆票。

### 第一級：已經分岔，或已經有使用者看得到的差異

#### S1 設定頁與健康頁讀同一份服務狀態，卻是兩支端點、兩份快取
- **是什麼**：`GET /settings/services`（`berth/api/settings.py:45-48`）和 `GET /health/detail`（`berth/api/health.py:53-56`）都是 `health_detail(await read_health(session))`，回同一個 `HealthDetailOut`。前端各有一組 query：`web/src/api/settings.ts:17` 的 `servicesQueryOptions` 和 `web/src/api/health.ts:19` 的 `healthDetailQueryOptions`。兩份快取**已經不同步**：`useServiceCheck.ts:20-21` 得兩把 key 一起寫；`HealthPage.tsx:48` 的「重新檢查」和 `recheckRoutes.ts:16` 都只更新 `['health', …]` 那一份。門禁不同（前者 admin、後者登入即可）不算理由，因為設定頁只有 admin 進得去，而 admin 本來就讀得到 `/health/detail`。progress.md 沒有記「要分成兩支」的決定。
- **建議**：留 `GET /health/detail`，刪 `GET /settings/services` 和 `servicesQueryOptions`；`HealthSection`、`useServiceCheck` 改讀 `healthDetailQueryOptions`。`POST /settings/services/{kind}/test` 不動。
- **大小**：小。後端兩個檔加 `test_auth_api.py:446` 門禁表那一列、`test_health_api.py:194-242`；前端三個檔，另有四個測試檔對這支打樁（`IndexerSettingsPage`、`JellyfinSettingsPage`、`QbittorrentSettingsPage`、`RouteRecheck` 的 test）；重跑 `gen:api`；同步 `docs/plan.md:391`、CHANGELOG。
- **風險**：刪一支對外 GET（消費者只有自家前端），照全域規則要先告知。不碰持久化資料。

#### S2 「這次請求為什麼失敗」判斷了兩處，其中一處對 500 和 401 給錯答案
- **是什麼**：`web/src/components/requestProblem.ts` 加 `RequestFailed` 依狀態碼分成 offline、invalid、conflict、server、signedOut 等（M4 票 21；progress.md:164「422 不再說『後端沒在跑』」）。另外大約 40 處是「拒絕原因解析不出來，就一律說 API 沒回應」：i18n 值的尾巴分兩種寫法，約 25 條寫 `Berth’s own API did not answer…`，約 15 條寫 `The Berth backend may be down…`；呼叫端例如 `issues/IssueRow.tsx:67`、`api/files.ts:50`、`plans/planRefusal.ts:8`，以及 `IssuesPage.tsx:58`、`JobsPage.tsx:58`、`ReviewPage.tsx:73` 的 `xxx.off`。**失效條件**：`POST /issues/{id}/resolve` 回 500 或 401 時，畫面說「Berth 自己的 API 沒有回應」；同一個錯誤交給 `RequestFailed`，會說「後端失敗，看 log」或「登入失效」。`api/refusal.ts:23-24` 說要落回「一句誠實的通用訊息」，現狀做不到。
- **建議**：拒絕解析不出來時，交給 `requestProblem` / `RequestFailed lead=…`，`lead` 說明什麼沒做成，尾巴只剩 `PROBLEM_TEXT`。這和票 21 在精靈與設定頁做的是同一件事，這次延伸到 issues、review、jobs、rss、media。四個整句相同的 key（`issues.failed`、`review.plan.failed`、`review.audit.failed`、`rematch.failed`）會順便收掉，但只收 key 解不掉分歧，不建議單獨做。
- **大小**：大（約 35 個呼叫端、約 80 個 zh/en 值，加上斷言整句文字的測試），建議拆兩張：先 issues/review，再 jobs/rss/media。
- **風險**：動 UI 文案，要使用者同意；500 和 401 的說法會改變，這正是要的效果。不碰對外介面與持久化資料。

#### S3 「Route 擁有哪條路徑」的「最深」有兩種量法，`owning_route` 那份在不正規路徑上會選錯
- **是什麼**：`services/claims.py:439-450` 的 `_route_of` 和 `services/routes.py:1355-1366` 的 `owning_route` 都是「對全部 Route 做 `is_within`，取最深的一條」。claims 用 `len(Path(...).parts)` 量深度，routes 用 `len(route.target_path)`，也就是字串長度。Route 的 `target_path` 存檔時不正規化（票 14a 有 `…/tv//anime` 這種 Route，測試也這樣釘住），所以 `/data/library/tv////` 對上 `/data/library/tv/anime` 時，字串長度會選錯。**`owning_route` 是有潛在錯誤的那份**，inventory、resolver、`routes._usage_of` 都呼叫它。
- **建議**：`owning_route` 改用 `len(Path(route.target_path).parts)`，`_route_of` 改成呼叫它，找不到才 raise `UnclaimedError`。補一個「不正規但較淺的 Route 對上較深的 Route」的測試。
- **大小**：小。
- **風險**：不碰對外介面；不正規路徑上的歸屬會改變，多數情況是修正。

#### S4 RSS 綁定的搜尋預填：前端手抄了後端的 `skeleton`，兩邊已經分岔
- **是什麼**：`web/src/rss/searchTerm.ts:9-15` 用 regex 從發佈名挑作品名，消費者是 `SeriesBinder.tsx:47`、`OneshotSection.tsx:232`。後端 `berth/parser/binding.py:89-119` 的 `skeleton()` 搭配 `search_terms` 做同一件事，而且比較完整。progress.md:1220 記過代價：「綁定框預填不拆季名（`searchTerm.ts` 是 `skeleton` 的前端手抄），Re:Zero 要人自己刪『第四季』」。另一個分岔例子：`[千夏字幕組][中文名_Romaji][第12話]` 在前端會退回整串原文，後端讀得出 `中文名`、`Romaji`。
- **建議**：後端在 `SeriesOut`（`api/rss.py:200`）和 oneshot 的 `OneshotItemOut`（`:323`）各加一格預填字串，取 `search_terms` 或 `skeleton` 在開票時決定；刪 `searchTerm.ts` 和它的測試，重跑 `gen:api`。
- **大小**：中。
- **風險**：API 回應多一個欄位（相容的新增）；不碰持久化資料。

#### S5 `reconcile._categories` 是 `qbittorrent.route_categories` 的逐字複本
- **是什麼**：`services/reconcile.py:394-395` 和 `services/qbittorrent.py:105-107` 一字不差。reconcile 已經從 qbittorrent import `managed` 等函式，而 `managed` 的 docstring（`qbittorrent.py:83-85`）寫的是「只有一份實作」。
- **建議**：刪 `_categories`，`reconcile.py:264` 改 import `route_categories`。
- **大小**：小。**風險**：無。

#### S6 `ParseContext.route_collection_type` 有人寫、解析器卻沒人讀
- **是什麼**：欄位定義在 `berth/domain/parser.py:647`，註解寫「劇集不能進 movies」。寫入有 `services/plan.py:492`、`services/search.py:634`、`tests/unit/test_parser_first_batch.py:254`、`scripts/experiments/first_batch_rule.py:55,94`、`scripts/fake_setup_server.py:2616`。`berth/parser/` 內沒有任何讀取。真正擋住劇集進 movies 的是 services 端的 `domain.collection_type_for`。這個欄位讓人以為解析器會依 Route 種類判斷，實際上不會。
- **建議**：刪欄位和所有寫入點（含 scripts）；`search.py:48` 的 `collection_type_for` import 只為這一行而存在，一併拿掉；同步 `docs/plan.md:285`。
- **大小**：小。**風險**：純內部，不經 API，也不持久化。

### 第二級：同一個判斷兩三份，現在答案一致，但改一處就會分岔

#### S7 區塊標題「h2 + 計數」：已經有元件，媒體頁等處又手寫了 10 份，無障礙寫法已經分岔
- **是什麼**：`web/src/rss/SectionHeading.tsx:9-35` 是元件，DESIGN.md:595-597 把它定為規格：`aria-hidden` 數字加上 `sr-only` 帶單位的句子。手寫版在 `media/SeasonsPanel.tsx:41`、`FilesPanel.tsx:56`、`SearchPanel.tsx:135`、`SubscribePanel.tsx:66`、`DownloadsPanel.tsx:171`、`WatchArea.tsx:135`、`discover/MediaWall.tsx:42`、`watching/WatchingRows.tsx:178`、`pages/InventoryPage.tsx:544`、`pages/JobDetailPage.tsx:178`。`SeasonsPanel.tsx:46` 的計數是裸的 `<p>{n}</p>`，螢幕閱讀器只念出「3」；`FilesPanel` 等處有補 `sr-only`。
- **建議**：把 `SectionHeading` 搬到 `components/`，媒體頁的區塊改用它。`SearchPanel` 的計數是一整句，走 `extra`；它的 heading ref 和 `tabIndex={-1}` 要保留。`WatchArea`、`WatchingRows` 靠右的連結也用 `extra`。頁級 h1 不併。
- **大小**：中（8～10 個檔）。**風險**：只動 markup。

#### S8 `JellyfinSetupOut.libraries` 前端沒讀；「媒體庫掛了 TVDB」的判斷寫了三份
- **是什麼**：`berth/api/setup.py:454-464` 的 `LibraryOut`（7 欄）只掛在 `JellyfinSetupOut.libraries`，`web/src` 沒有任何地方讀它（頁 3 讀的是 `RouteSetupOut.libraries`）。它在 services 的來源是 `services/jellyfin.py:185` 的 `LibraryView`、`:205` 的 `JellyfinSetupView.libraries`、`:1107` 的 `_library_view`。另外，「有沒有 TVDB」的判斷有三份：`jellyfin.py:134` 的 `tvdb_fetchers()`，以及行內寫在 `jellyfin.py:1114`、`routes.py:1380` 的 `any(TVDB_MARKER in name.lower() …)`，後兩處逐字相同。
- **建議**：拿掉 `JellyfinSetupOut.libraries`、`LibraryOut`，連同 services 的 `LibraryView`、`_library_view`、`JellyfinSetupView.libraries`；資料庫快照 `setup.jellyfin.libraries` 照留。再加一個同步函式 `uses_tvdb(names)`，讓 `tvdb_fetchers` 和 `routes._library_choice` 共用。測試要改：`test_setup_api.py:629,692-694`；`test_setup_jellyfin.py:290-308` 改斷言 `LibraryChoice.berth_path`。
- **大小**：小～中。**風險**：API 回應形狀會變（前端沒讀），要重跑 `gen:api` 並改 `src/test/fixtures.ts`；不碰持久化資料。
- 不做的部分：worker 提議把 `LibraryView` 和 `LibraryChoice` 兩個 dataclass 合併，複核駁回，因為兩者是不同步驟的回應形狀，只是有六個欄位重疊。

#### S9 「Route 的 Jellyfin 媒體庫：先比 id、沒有 id 才比名字」寫了三份
- **是什麼**：`services/routes.py:1227` 的 `_library_key`、`routes.py:1236` 的 `_is_library(library, plan_row)`、`services/health_issues.py:123` 的 `_is_library(library, route)`。`health_issues.py:95` 的 docstring 寫「`services/routes._is_library` 的同一條規則」，自己承認有兩份。
- **建議**：`routes.py` 留一支 `route_library_matches(library, library_id, library_name)`，三處都改呼叫它。改成 health_issues import routes 不會造成循環 import。
- **大小**：小。**風險**：無。規則一旦改了，健康檢查和建立 Route 的流程不會各說各話。

#### S10 「現在幾點（UTC）」有四份實作，另有四處行內寫法
- **是什麼**：`models/types.py:55` 的 `utcnow()` 已經有 17 個 services 模組在用，但 `services/auth.py:234`、`health.py:508`、`setup.py:1130` 又各自定義了一模一樣的 `_utcnow()`；`discover.py:247,254`、`media.py:336,365` 則直接寫 `datetime.now(UTC)`。測試沒有 monkeypatch 這三個 `_utcnow`。
- **建議**：刪三個 `_utcnow`，八處都改 import `utcnow`。pipeline 的注入時鐘預設值，以及 `reconciling.py:43` 用本地時間的那一處，語意不同，不要一起換。
- **大小**：小。**風險**：無。

#### S11 「已交給 qBittorrent、還沒完成」的狀態集合定義了兩次
- **是什麼**：`services/downloads.py:98` 的 `IN_CLIENT_STATES` 和 `services/jobs.py:1017` 的 `IN_FLIGHT` 內容相同，註解也各自重述一遍。之後新增客戶端內的狀態時，兩份都要改。
- **建議**：保留一份放在 `jobs.py`（downloads 已經 import jobs，不會循環），刪 `IN_FLIGHT`。`ESTIMABLE`、`ACTIVE_STATES` 等回答的是不同問題，不必從它推導（複核駁回了 worker 的這部分建議）。
- **大小**：小。**風險**：無。

#### S12 qBittorrent 自己寫了一份版本字串解析，`adapters/versions.parse_version` 已經有了
- **是什麼**：`berth/adapters/qbittorrent/__init__.py:587-595` 的 `_parse`（呼叫點 `:81,86,94`）和 `adapters/versions.py:8-17` 的 `parse_version`。後者的 docstring 寫明 Jellyfin 和 Prowlarr 共用。兩者的邊界行為略有不同，但 webapi 版本字串已經在 `client.py:97` 先 strip 過，比較下限時結果相同。
- **建議**：改用 `parse_version`，刪 `_parse`；驗收時跑 `tests/unit/test_adapters.py:339-359`。
- **大小**：小。**風險**：無。

#### S13 「沒登入的人算 system」這個決定在 API 層寫了 11 遍
- **是什麼**：`actor_of(user.id if user is not None else None)` 行內寫了 10 處：`files.py:153`、`issues.py:242,261`、`jobs.py:442,516`、`review.py:334,351,365,380,404`。另外 `plans.py:298` 有一支 `_actor(request)`。
- **建議**：把 `plans._actor` 移到 `api/gate.py`，放在 `current_user` 旁邊，各處改呼叫它。
- **大小**：小。**風險**：無。

#### S14 「服務還在啟動，每 3 秒重測」的 effect 寫了兩份，寫法已經分岔
- **是什麼**：`pages/SetupPage.tsx:417-419,510-517` 和 `settings/ServiceConnection.tsx:69-75`；後者的註解寫「照精靈」。SetupPage 把整個 `retest` mutation 物件放進 effect 的相依；TanStack Query 5 的 `useMutation` 每次 render 都回傳新物件，所以 SetupPage 只要重新 render，3 秒計時器就會被重設。ServiceConnection 解構出穩定的 `mutate`，沒有這個問題。這會不會造成使用者看得到的延遲，目前沒有 repro，不宣稱是 bug。
- **建議**：在 `setup/` 抽一個 `useWaitingRetest(waiting, busy, retest)`，兩處共用。
- **大小**：小。**風險**：低。

#### S15 `CjkHints.hardsub` 和 `CjkHints.subtitle_kind` 是同一件事的兩種表示
- **是什麼**：`parser/cjk.py:232-240` 的 `_take_subtitle_kind` 同時回傳兩個值，前者可以由後者推出。產品程式碼只讀 `subtitle_kind`（`release.py:149`）；`.hardsub` 的其他讀取都是另一個欄位 `Tags.hardsub`。`CjkHints.hardsub` 只有 `tests/unit/test_parser_cjk.py:61,67,73,80` 在讀。
- **建議**：刪欄位，`_take_subtitle_kind` 改成只回 `SubtitleKind`，測試改斷言 `subtitle_kind`；同步 `docs/plan.md:271`。
- **大小**：小。**風險**：純內部。

#### S16 `ReleaseInfo.video_codec` / `bit_depth` / `audio` 有解析、沒人讀
- **是什麼**：`domain/parser.py:539-541` 的三個欄位在 `parser/release.py:145-147` 由 guessit 填入。`ReleaseInfo` 沒有離開 parser：services 只取 `.group/.episode/.title_candidates` 或經 `tags_of`；`job_files.release_info_json` 也早就不寫了（progress.md:821）。三格沒有任何讀取，容易被誤認為「已支援依編碼挑版本」。
- **建議**：刪三個欄位與 `release.py` 那三行。`docs/design-brief.md:207`（§6.3）把它們列為 ReleaseInfo 的規格欄位，所以要同一個 commit 改 brief §6.3，並在 progress.md「偏差與決定」記一行。適合和 S15 併成同一張票。
- **大小**：小。**風險**：純內部，不經 API、不持久化；動到 brief。

#### S17 TMDB 錯誤對應到 `TmdbProblem` 寫了兩份
- **是什麼**：`services/discover.py:158-171` 和 `services/media.py:211-229` 各寫一次「缺憑證 → `CREDENTIAL_MISSING`、`AuthFailedError` → `CREDENTIAL_REJECTED`、`ServiceError` → `UNREACHABLE`」。`TmdbProblem` 的 docstring（`domain/enums.py:34-35`）寫明合成一個 enum，就是怕兩份走樣。
- **建議**：加 `tmdb_problem(exc)`，只處理三種共同錯誤；`media.py` 的 `NotFoundError` 分支留在原處，放在共用呼叫之前。`NotFoundError` 是 `ServiceError` 的子類，共用函式如果也收 NotFound，探索頁的 404 就會從 `UNREACHABLE` 變成 `NOT_FOUND`。要不要一起改，由使用者決定。
- **大小**：小。**風險**：照上面的做法沒有。

#### S18 搜尋結果預估自己組季集代號，沒用 `components/episodes.ts`
- **是什麼**：`media/searchResult.ts:62-71` 手寫 `S${pad(x)}`、`E${pad(x)}`，自己的 `pad` 在 `:103-105`。`components/episodes.ts:13-19` 的 `seasonCode` / `episodeCode` 是單一來源，檔頭寫「同一個代號各寫一份遲早會分岔」。
- **建議**：改用 `seasonCode` / `episodeCode`，刪 `pad`。畫面輸出一字不變（`searchResult.test.ts:55` 照樣綠）。
- **大小**：小。**風險**：無。
- 不做的部分：範圍的寫法現在有三種（`formatEpisode` 用 `-`、`formatCoverage` 用 `S01 E01–E28`、`estimate` 用 `S03E01–E13`），要不要統一屬於文案或設計決定，見〈範圍外觀察〉。

#### S19 單選篩選列的 markup 有三份
- **是什麼**：`pages/JobsPage.tsx:112-125`、`pages/InventoryPage.tsx:700-725`、`media/DownloadsPanel.tsx:73-90` 結構相同，選中的那顆都是 `<span aria-current="true" className={`${FILTER_ACTIVE} text-ink`}>`。`JobsPage.tsx:106` 註明「與媒體庫的篩選同一條」。DESIGN.md:633-635 規定「選中的那個不是連結」。
- **建議**：做一個 `components/FilterBar.tsx`，非選中的按鈕用 render prop 畫，重複的 `text-ink` 收進元件；`InventoryPage` 的 `activeOptions={{exact: true}}` 要帶過去。
- **大小**：小。**風險**：低。

### 第三級：確定、便宜、零風險的清理

#### S20 「精靈跑完了沒」有三個出口，前端只讀其中一個
- **是什麼**：前端只讀 `Health.setup_completed`（`web/src/routes.tsx:74`；`api/health.py:36-38` 的註解說明它必須掛在匿名端點上）。`SetupStatusOut.completed`（`berth/api/setup.py:143`）和 `RouteSetupOut.completed`（`:977`）前端都沒讀，它們在 services 的來源 `SetupStatus.completed`（`services/setup.py:144,1095`）和 `RouteSetup.completed`（`services/routes.py:197,226`）也只有 API 和測試讀。
- **建議**：兩個 API 欄位和兩個 services view 欄位一起刪；資料庫的 `SetupSettings.completed` 不動。要改的斷言在 `test_setup_api.py:98,1275`、`test_settings_take_over.py:118`、`test_setup_owned_writes.py:571`、`test_setup_owner.py:97`、`test_setup_routes.py:1279`。
- **大小**：小。**風險**：API 回應形狀會變（前端沒讀）。

#### S21 前端死碼：knip 抓到的 11 項，加上多餘的 export 23 項
- **是什麼**：完全沒人用的有 9 個 type：`Role`（`api/auth.ts:7`）、`IssueType`、`ReconcileSide`（`api/issues.ts:11,31`）、`RouteChoice`（`api/media.ts:17`）、`PlanStatus`、`Confidence`（`api/plans.ts:15,21`）、`AuditSeries`（`api/review.ts:18`）、`SkipCode`（`api/rss.ts:29`）、`Tags`（`api/search.ts:13`）。另有 `stubJsonResponse`（`test/fetch.ts:6`，連測試都沒呼叫）、`SERVICE_KINDS`（`api/schemas.ts:59`，註解寫「泊位板逐格照它畫」，但已經不是事實，泊位板走 `components/berths.ts`）。`TOTAL_STEPS`（`setup/navigation.ts:32`）只有一條 `expect(TOTAL_STEPS).toBe(6)` 守著，而同一個 `it` 已經用 `toEqual` 斷言整個 `STEP`。其餘 23 項是「同檔有用，只是不必 export」，清單見附錄 A。
- **建議**：刪掉上面 12 項（`TOTAL_STEPS` 連那行 expect 一起刪），23 項拿掉 `export`。這張做完，knip 才能當閘門（見〈閘門建議〉）。
- **大小**：小（約 15 個檔，每處一兩行）。**風險**：無。不動 `schema.d.ts`。

#### S22 `Config.data_root` 沒有人讀，文件把它寫成 Berth 會讀的變數
- **是什麼**：`berth/config.py:40,65` 讀環境變數 `DATA_ROOT`，`deploy/Dockerfile:46` 也有設，但產品程式碼沒有任何地方讀 `Config.data_root`。Berth 的根目錄來自資料庫 `PathSettings` 的預設值（`models/setting.py:138-143`；`plan.md:591`）。讀它的只有 `tests/unit/test_config.py` 和 `scripts/fake_setup_server.py:2029`。`docs/development.md:46` 寫它是「媒體根：incomplete、complete 與媒體庫路徑都在它底下」，`plan.md:30` 也把它列為 Berth 的路徑常數。
- **建議**：刪 `Config.data_root` 和 Dockerfile 那行 ENV。compose 主機端的 `${DATA_ROOT}` 掛載和 `.env.example` 是另一回事，照留。`development.md:46` 改成明講 `DATA_ROOT` 只給 compose 掛載用；同步 `plan.md:30`、CHANGELOG。
- **大小**：小。**風險**：屬於設定項變動，但行為不變，因為現在這個值本來就沒有作用。

#### S23 `IndexerResult.leechers` 和 `FakeIndexerSearch.closed` 沒有人讀
- **是什麼**：`adapters/indexer/__init__.py:56` 的 `leechers` 由 `indexer/prowlarr.py:94` 填入，搜尋結果只帶 `seeders`，讀它的只有 `test_indexer_search.py:44`。`adapters/indexer/fake.py:40,65` 的 `closed` 只寫不讀。
- **建議**：兩者都刪。傳 `leechers=` 的還有 `test_search_api.py:56,70,82,90`、`scripts/fake_setup_server.py:714,725`。
- **大小**：小。**風險**：無。

#### S24 pipeline 有沒人用的 `Waiter`，`Sleeper` / `Clock` 別名重複定義四次
- **是什麼**：`pipeline/planning.py:34` 的 `Waiter` 在整個 repo 只有定義。`Sleeper` / `Clock` 在 `pipeline/{downloads,health,reconciling,rss}.py` 各定義一次。
- **建議**：刪 `Waiter`；pipeline 的四份別名收到 `pipeline/ticks.py`。`adapters/budget.py:30`、`services/indexer.py:92` 那兩份受依賴方向限制，不能從 pipeline import，先不動。
- **大小**：小。**風險**：無。
- 不做的部分：七個迴圈的 `run()` 骨架長得一樣，但真正會影響結果的判斷（`is_setup_complete`、`whole_tick`）已經各只有一處，剩下的只是寫法相同，複核駁回。

#### S25 前端四處小型手抄：每處都已經有共用版本
- **是什麼**：
  - `pages/MediaDetailPage.tsx:348-353` 的類名逐字等於 `<Notice signal="neutral">`（`components/controls.tsx:264-282`）。
  - `pages/MediaDetailPage.tsx:90` 的 h1 類名逐字等於 `PAGE_TITLE`（`controls.tsx:233`），而 `PAGE_TITLE` 就是為了讓各頁 h1 不再各寫各的（progress.md:85）。
  - 排隊清單的「讀取中」佔位有三份：`IssuesPage.tsx:80-87`、`ReviewPage.tsx:171-178`、`InventoryPage.tsx:659-666`，註解互相寫「同 /issues」「同 /review」。
  - `media/FilesPanel.tsx:439-441` 的 `baseName` 和 `components/queueText.ts:4-7` 的 `fileName` 做同一件事。
- **建議**：前兩處改用 `Notice`、`PAGE_TITLE`；佔位抽成 `components/QueueLoading.tsx`（`max-w-[80rem]` 交給呼叫端）；`FilesPanel` 改用 `fileName`。
- **大小**：小（一個 session 可以全部做完）。**風險**：無。

### 第四級：成立，但值得度低

#### S26 「還沒選服務來源，就當成既有服務」這條規則散在多處
- **是什麼**：`routes._jellyfin_origin`（`routes.py:1308`）、`health.py:486` 行內、`setup.py:1059`，以及兩個 `_refuse_existing`（`qbittorrent.py:332`、`indexer.py:655`）。`ServiceOrigin` 目前只有兩個值，所以 `is not BUNDLED` 和 `(origin or EXISTING) is EXISTING` 等價；之後加第三種來源，這些地方就會各說各話。`services/deeplink.py:49` 的註解指向一個已經不存在的 `health._origin`。
- **建議**：在 `SetupSettings` 加一支 `origin_or_existing(kind)`，給 routes 和 health 共用；只問「是不是套件內」的 `is not BUNDLED` 幾處不必動；deeplink 的註解改指新函式。
- **大小**：小。**風險**：無。

#### S27 作品資料夾名的 TMDB id 反解寫在 naming 以外
- **是什麼**：`services/claims.py:83` 的 `_TMDB_ID` regex 反解 `naming.FOLDER_TEMPLATE`（`naming/__init__.py:19-21`）。模板改了的後果是「認不出」，不會「認錯」，因為 `claims.py:347` 之後還會用 `read_target` 重算核對。
- **建議**：在 naming 加 `tmdb_id_of(folder)`，claims 改呼叫它。
- **大小**：小。**風險**：無。

#### S28 `classify` 同一個檔案裡有兩種寫法判斷「是不是影片副檔名」
- **是什麼**：`parser/classify.py:124` 的 `kind_by_extension()` 和 `:172` 行內的 `_BY_EXTENSION.get(extension(...))` 查同一張表。只要 `kind_by_extension` 加了特例，`_biggest_video_per_directory` 就不會跟著改。
- **建議**：第 172 行改呼叫 `kind_by_extension`。可以併進下一張碰 classify 的票。
- **大小**：一行。**風險**：無。

#### S29 三個 `__init__.__all__` 重新匯出了包外沒人用的名稱
- **是什麼**：包外完全沒人用的：parser 的 `SAMPLE_RATIO, VIRTUAL_SEASON_GAP, VOUCHED, MediaMatch, Misfit, SubtitleMatch, langs_in`；domain 的 `CONFIDENCE_ORDER, LANG_ORDER, ReasonParams`；models 的 `DEFAULT_INTERVAL_SEC, SetupTmdb`。名稱有人用、但沒人經由包路徑取用的：parser 的 `StructureHints, matches, SHORT_FEATURE, match_subtitle`；models 的 `HARDLINK, SetupIndexer, SetupJellyfin`。這些名稱在各自的模組內都還在用。
- **建議**：從 `__all__` 和 `__init__` 的 import 拿掉。
- **大小**：小。**風險**：無。

#### S30 三套「code + params 的理由」模型與建構函式逐字相同
- **是什麼**：`domain/parser.py:379-401`（`ItemReason`/`why`）、`domain/binding.py:91-105`（`BindReason`/`because`）、`domain/screening.py:56-66`（`SkipReason`/`skipped`）。`frozenset(params) != X_PARAMS[code]` 的檢查剛好出現在這 3 處，「不能有 `count` 鍵」的規則也在三處註解各寫一次。docstring 只寫「形狀照 X」，沒寫為什麼不共用。
- **建議**：抽一個泛型基底或小工廠；code enum、參數表、i18n 命名空間仍各自保留。JSON 形狀不能變（`plan_items.reasons_json` 已經持久化，也是 API 的對外形狀）。
- **大小**：中。**風險**：只動 Python 就不碰 API 和持久化資料。值得度低：重複的是樣板，不是判斷。

#### S31 狀態色塊在約 55 處手寫同一串類名，而且漂出第四種內距
- **是什麼**：除了 `components/AuditChip.tsx`，其他地方都手寫 `label px-? py-? ${SIGNAL_FILL[x]}`。DESIGN.md:556-560 只定義三種內距（標準 `px-2 py-1.5` 27 處、compact `px-1.5 py-0.5` 15 處、時間線 `px-1.5 py-1` 2 處），另外 11 處 `px-2 py-1` 色塊不屬於任何一種：`SubscribePanel.tsx:110,119`、`RssPage.tsx:99`、`FirstRoundSection.tsx:47`、`ItemLine.tsx:67`、`SeriesSection.tsx:181`、`BundledLibraries.tsx:220`、`IndexerSites.tsx:275,774`、`RecommendedSites.tsx:145,196`。
- **建議**：先由使用者決定那 11 處歸到標準還是 compact，這是設計決定。之後照 `controls.tsx` 現有的類名常數慣例（`FILTER`、`NAV_BOX`、`COMPACT_BUTTON`）加 `CHIP` / `CHIP_COMPACT`，逐處替換。
- **大小**：大（約 55 處，都是機械替換，可以拆兩個 session）。**風險**：那 11 處的高度會微調，要實跑看一眼。

### 需要使用者先決定：動到 API 回應形狀或持久化資料

#### S32 API 回應欄位前端沒讀
- **是什麼**：在 `web/src` 和 `web/e2e`（排除 `schema.d.ts`、測試、i18n）逐欄搜尋，讀取點都是 0：
  - `DeletionEstimateOut.link_bytes`、`source_bytes`（`api/jobs.py:284,288`；來源 `services/deletion.py:92,96,136,139`）。`reclaimable` 是獨立算出來的，刪掉這兩欄不需要另留局部變數。
  - `JobOut.route_slug`（`api/jobs.py:188`；來源 `services/jobs.py:288,1416`）、`trigger_ref`、`user_id`、`completed_at`、`imported_at`。
  - `BudgetOut.window_seconds`（`api/health.py:97`）、`SiteBudgetOut.frees_at`、`DeferralOut.since`（`plan.md:404` 的 `GET /health/budget` 描述寫了「放得下的時刻」，刪時要同步改）。
  - `ItemOut.seen_at`（`api/rss.py:298`）、`BangumiOut.premiere`（`api/rss.py:590`；`plan.md:402` 把它寫進回應形狀，刪時要同步改）、`UnmatchedRowOut.file_kind`（`api/review.py:213,480`）。
  - `JobOut.content_path`：前端沒讀，但真實服務的 e2e 靠它找檔案（`tests/e2e/test_1_m1_pipeline.py:98,126`、`test_3_m2_repair.py:159`）。刪了 e2e 就得改用 `save_path` 加 `name` 自己組路徑，風險是中，建議維持現狀。
  - `PlanOut.engine`、`engine_version`（`api/plans.py:170-172`）：可能和 M5「AI 提案還是規則提案」有關，但文件沒有寫明要留，**由使用者決定**。
- **建議**：使用者勾選的欄位，從 `*Out` 拿掉；services 的欄位和資料庫不動。後端斷言要改的有 `test_jobs_api.py:310`、`test_plans_api.py:276`、`test_health_api.py:342`、`test_deletion.py:474,489`；前端 fixture 有 `JobDelete.test`、`JobDetailPage.test`、`JobsPage.test`、`MediaDetailPage.test`、`SearchPanel.test`。
- **大小**：中。**風險**：API 回應形狀會變（消費者只有自家前端）；不碰持久化資料。

#### S33 只寫不讀的資料庫欄位
- **是什麼**：以下各欄只有寫入；產品程式碼、API 回應、`schema.d.ts` 都沒有讀取：
  - `jobs.last_seen_in_client_at`（`models/job.py:71`；寫在 `claims.py:234`、`downloads.py:458`）。註解說要在「torrent 從客戶端消失時」用，但這個消費者不存在。
  - `plans.decided_by` / `decided_at`（`models/plan.py:55-56`；寫在 `plan_review.py:161-162,190-191`、`rematch.py:603-604`）。`decided_by` 只有測試讀。
  - `ledger.source_inode`（`models/ledger.py:54`；寫在 `claims.py:359`、`importer.py:373`、`issues.py:379,475`）。只有測試讀；判斷 inode mismatch 和刪除檢查用的是 `source_dev` 加 `target_inode`（`deletion.py:368`）。
  - `ledger.link_mode`（`models/ledger.py:81`）：值永遠是 `hardlink`，只有測試讀。刪了它，`HARDLINK` 常數和它的 re-export 也就沒用了。
  - `users.last_login_at`（`models/auth.py:26`；寫在 `auth.py:196`），只有測試讀。
  - `job_files.updated_at`（`models/job.py:96`）：只在 `plan.py:561`、`reimport.py:129` 兩條路徑寫入，其他更新 job_files 的路徑都不寫，所以欄位的語意本身就說不清。
  - `settings.updated_at`（`models/setting.py:37`）：ORM 的 `onupdate` 自動寫入，沒有人讀。
- **建議**：二選一。(a) 刪：寫一支 migration，刪所有寫入點和測試斷言。ledger 用 SQLite 原生 `DROP COLUMN`，**不要用 batch 重建**：`7c3e5a9b2d41` 的 docstring 記載 batch 重建時外鍵順序不固定，會讓降版再升版的 schema 比對測試失敗。`source_inode` 是 NOT NULL，沒有 default，另有 11 處建列的 tests/scripts 要改。(b) 保留：把它們當稽核欄位，只在 `docs/plan.md:105,127,131,134` 寫明用途。`job_files.updated_at` 的語意已經說不清，傾向至少刪這一欄。
- **大小**：中（一支 migration 加十幾處寫入點）。
- **風險**：**動到持久化資料和 migration**，照 CLAUDE.md 要先告知；`plans.decided_*` 是 plan 文件承諾過的欄位。

#### 成立但建議不動
- `issues.Recorded.issue`（`services/issues.py:110`）：產品程式碼只讀 `.opened`，`.issue` 只有 6 個測試檔在讀。不過命令回傳「這次寫入的那一列」本來就是自然的形狀，M5 的命令登錄表也會要這個結果。如果要符合「刻意接縫」的標準，在 docstring 補一句就好。

## 文件與註解偏差（順手發現，不是程式碼）

一張小票就能全部修完：

- `docs/plan.md:52` 寫 `cli.py` 有 `berth reconcile`。實際只有 `serve / openapi / bench / rebuild-ledger`；`git log -S` 查不到這個子指令實作過。手動對帳的入口是 `POST /api/issues/reconcile`。同一行還漏了 `serve`、`openapi`。
- `docs/development.md:46`、`docs/plan.md:30` 的 `DATA_ROOT`：見 S22。
- `services/events.py:62-63`：`EventHub.subscribers` 的 docstring 說健康頁靠它，但讀它的只有測試，應改成「只給測試」。
- `services/deeplink.py:49`：註解指向不存在的 `health._origin`，見 S26。
- `domain/enums.py:1011`：`PlanEngine.AI` 的註解還寫「M4」，AI 任務在 2026-09-24 已經移到 M5（progress.md:15）。
- `services/plan.py` 的 `_duplicate_of` docstring 說「判準與同一包那一半共用 `parser.episode_span`」，但帳本那一側（`plan.py:727,735`）是行內算的。

## 刻意保留（不算發現，附理由出處）

| 項目 | 出處 |
| --- | --- |
| 季名寫法三個讀者共用一份字串 | `berth/parser/seasons.py:1-6` |
| 發佈時間窗口：mapping 與 first_batch 共用 | `berth/parser/publishing.py:1-6,27-29` |
| `naming.extension` 給分類與目標檔名共用 | `berth/naming/__init__.py:278-284` |
| `naming` 的反解（`read_target` 等）用同一組模板重算，不是第二套規則 | `berth/naming/__init__.py` 的 `Reading` docstring（約 :300-307） |
| `naming.episode_target` 與 `domain.episode_label` 各組一次 `S01E02` | 一個是 Jellyfin 檔名合約，一個是理由與畫面用的機器字串：`naming/__init__.py:3-5`、`domain/parser.py:403-406`（原 B7，複核駁回，理由同此） |
| `mediainfo` 領域模型住在 `domain/` | `berth/domain/mediainfo.py:1-8` |
| `MediaInfoSummary` 的寬高、編碼、音軌、字幕欄位沒人讀 | 等「解析度改讀 mediainfo」等消費者：progress.md:919、brief:150,181,271、plan.md:561 |
| `PlanEngine.AI` 沒有引用 | M5 自動模式套用的 Plan 需要它：plan.md:322、brief:159、plan.md:131；它也在 API 型別裡 |
| `adapters/ai.py` 的 `AiPlanner` / `NullAiPlanner` 只有測試用 | `docs/plan.md:322`（「至今沒有呼叫端」，M5 核心） |
| `models/setting.py` 的 `RETIRED_FAILURES` 相容分支 | `berth/models/setting.py:202,225-230`（舊設定檔仍可能有這些值） |
| `jobs.held_locks` 只給測試 | `berth/services/jobs.py:227-229` |
| `EventHub.subscribers` 只給測試 | `berth/services/events.py:62-63` docstring（「測試靠它確認訂閱真的收掉了」；同一句說健康頁也靠它，不實，見〈文件與註解偏差〉） |
| `commands.mark_of` | `tests/unit/test_command_marks.py` 與 CLAUDE.md 架構規則；M5 登錄表（plan.md:986） |
| `qbittorrent.managed` / `unknown_torrents` / `unknown_torrent_detail` 由 poller 與 reconcile 共用 | `berth/services/qbittorrent.py:83-85,94-96,112-114` |
| `bench.py` 以 `Bucket` 名稱動態存取欄位 | `berth/services/bench.py:129,351,404` |
| 各 router 的 `XRefusalOut` + `_STATUS` 樣板、`review.py` 的四個 `*ReasonOut` | 每個拒絕 enum 一個 model，讓 OpenAPI 產出封閉集合：`berth/api/files.py:195-196`、progress.md:84、`tests/unit/test_openapi_contract.py` |
| `GET /jellyfin/libraries` 與 `POST /setup/routes/libraries` 兩份媒體庫清單 | progress.md:871（新增 Route 時向 Jellyfin 現查，不讀第 3 步的快照） |
| `berth rebuild-ledger` CLI 與 `POST /issues/rebuild-ledger` | plan.md:866、progress.md:203 |
| 三條 confirm 端點 | 單筆有 409，批次跳過：`berth/api/review.py:343-349` |
| `/settings/services/{kind}/test`、`/setup/services/{kind}/test`、`/health/check` | `web/src/api/settings.ts:8-14`、progress.md:118 |
| `deleteSetupRoute` 與 `deleteRoute` | `web/src/api/setup.ts:382-385`（精靈跑完前沒人登入得了） |
| `setup/BerthBoard.tsx` 與 `components/BerthBoard.tsx` | `web/src/setup/BerthBoard.tsx:13-19` |
| 兩個 `STATUS_SIGNAL` | 值域不同：`web/src/inventory/InventoryTile.tsx:18-23` |
| `Timestamp` 與 `whenText` | `web/src/components/queueText.ts:9-12`（同一個語言規則） |
| `formatCoverage` 用 en dash | `web/src/components/episodes.ts:48-53`、DESIGN.md:875 |
| 各 `api/*.ts` 的 `REASONS` 表 | `web/src/api/refusal.ts:8-13`（少一種就編譯錯誤，這就是閘門） |
| `CONFIRM_ACTIONS` / `ConfirmPanel` | `web/src/components/controls.tsx:318-326` |
| `InventoryPage` 手寫 debounce，不用 `useDebounced` | `web/src/pages/InventoryPage.tsx:288-289`（只有打字才該換網址） |
| 「這支端點不存在」的兩條否定測試 | 守的是仍然有效的產品決定，而且是唯一的閘門：`tests/integration/test_media_api.py:128-129`、`test_setup_api.py:1057,1067`、`berth/api/setup.py:941` |
| `tests/e2e/payload.py` 另定義一份 `SHORT_FEATURE` | `tests/e2e/payload.py:15,47`（容器裡只有標準庫，沒有 Berth） |

另外查過、**本來就不是重複或死碼**（沒有成文理由，也不需要）：discover、media、sources 三種 TTL 快取存的東西與過期語意不同（`sources.py` 模組 docstring、`media.py:62,67`、`discover.py:39`）；`adapters/*/fake.py` 的公開介面（`revoke_api_key`、`signs_in`、`LIBRARY_SCAN_TASK` 等）都有測試在呼叫（例如 `tests/integration/test_issue_repairs.py:23,384`），逐條見 `C-review.md`〈工具判定抽查〉。

## 複核駁回（查過、不列）

| 原編號 | 主張 | 駁回理由 |
| --- | --- | --- |
| B7 | `naming` 與 `episode_label` 各組一次 `S01E02` | 兩者不是同一件事，見〈刻意保留〉 |
| A8 | `job_context` + `job_lock` 的組合重複約 10 處 | 兩個可以組合的原語，`rematch.locked` 是多筆排序取鎖的版本，屬寫法偏好；只有 `issues._replan` / `_restart` 真的少了 `job_context`，見〈範圍外觀察〉 |
| A11 | `PAGE_SIZE = 50` 定義兩次 | 兩個獨立可調的數，inventory 那一份有自己的理由（M2 票 13） |
| A2 部分 | `ESTIMABLE`、`ACTIVE_STATES`、`settled` 改由同一組推導 | 回答的問題不同，只是目前剛好可以推出 |
| A3 部分 | 合併 `LibraryView` 與 `LibraryChoice` | 不同步驟的回應形狀 |
| C6 部分 | 七個 pipeline 迴圈的 `run()` 骨架 | 判斷已經各只有一處，剩下的是寫法 |
| C7 部分 | `JellyfinWebOut.model_validate(await jellyfin_web(...))` 四份 | 單行包裝，沒有判斷可以分岔 |
| C10 | 兩條「端點不存在」的測試 | 改判刻意保留，見上表 |
| A 疑點 | `episode_end or episode_start` 散在各處、三種「同一集」判準 | 前者是單集資料的表示慣例；後三者回答不同問題 |
| D 疑點 | 空狀態抽 `EmptyState` | 外框都照 DESIGN.md:600 同一個規格，內容各不相同 |
| D 疑點 | `formatSize` / `formatCount` 擺在 `media/` | 擺放問題，不屬於本票的兩類 |

## 範圍外觀察（不屬於兩類，記給使用者）

- `services/issues.py:524`（`_replan`）、`:602`（`_restart`）拿了鎖，但沒有設 `job_context`，所以這兩條路徑的 log 沒有 job 欄位。這是可觀測性的缺口。
- 季集範圍有三種寫法（`S03E01-E02`、`S01 E01–E28`、`S03E01–E13`），只有 `formatCoverage` 寫了理由。要不要統一是文案或設計決定。
- 媒體庫頁的 h1 用 `.label`（`pages/InventoryPage.tsx:92`），其他頁用 `PAGE_TITLE`。DESIGN.md:344 寫區塊的 h1/h2 都用 `.label`，和 `controls.tsx:229-233` 互相矛盾，要先決定頁級 h1 用哪一種。

## 閘門建議：要不要把 vulture、knip 加進 pre-commit

**結論：knip 值得加，但要先做 S21；vulture 不建議加。**由使用者決定。

### knip（前端）

- **準確度**：39 條裡 34 條成立（11 條完全沒人用、23 條是多餘的 export），5 條誤報：`uv` 是 `gen:api` 用到的外部 binary，另外 4 條是產生出來的 `schema.d.ts` 裡的 `paths / webhooks / $defs / operations`。**誤報率 13%**，而且 5 條都能用兩行設定排除，排除後沒有誤報。沒有出現 Unused files 或 Unused dependencies，代表入口辨識正常。
- **要加的 whitelist**：`web/knip.json` 加兩項：`"ignoreBinaries": ["uv"]`，以及 `"ignoreIssues": {"src/api/schema.d.ts": ["exports", "types"]}`（knip 官方設定，查 knip.dev/reference/configuration）。另外要決定一件事：如果想保留「同檔使用也 export」的寫法，可以開 `ignoreExportsUsedInFile: true`，那 23 條就不會再報；若想讓 export 面保持最小，就不開，照 S21 拿掉 export。
- **代價**：跑一次約 1.7 秒。knip 目前不在 `web/package.json`，要加成 devDependency 並鎖版本（這次用的是 6.41.0）。pre-commit 加一條 `pnpm -C web exec knip`，`files: ^web/`。
- **前提**：現在的樹上有 34 條，閘門一開就是紅的，所以先做 S21，或同一張票一起做。

### vulture（Python）

- **準確度**：用的指令是 `uvx vulture berth tests scripts --exclude berth/migrations --ignore-decorators "@router.*,@field_validator,@model_validator"`，預設信心門檻 60。
  - 連測試都沒用（159 條）：15 條成立，其餘 144 條是誤報，**誤報率 91%**。
  - 只有測試在用（只掃 `berth` 的 313 條減掉上面那 159 條，得 154 條）：29 條成立、9 條是刻意的測試接縫、116 條誤報，**誤報率 75%**。
  - 誤報大宗是 pydantic 回應欄位：前端從 JSON 讀，vulture 看不到。其次是 `model_config`、SQLAlchemy `TypeDecorator` 回呼、`HTMLParser.handle_*`、`__aexit__` 簽章、`bench.py` 的字串動態存取。
  - 門檻拉到 61 以上只剩 5 條，全部是 `__aexit__` 參數和測試裡沒用到的變數，等於什麼都沒抓到。
  - 成立的條目幾乎都是「API 欄位前端沒讀」和「ORM 欄位只寫不讀」，**vulture 本身判斷不了這兩種**，這次靠的是 worker 拿欄位名去 grep `web/src`。函式、類別、方法層級的結果，在掃了 tests 之後只剩 9 條 `handle_*`，全部是誤報。
- **要加的 whitelist**：要讓現在的樹變綠，得白名單掉約 144 條（或寫一批 `--ignore-names` 模式）。以後每加一個 API 回應欄位，都要再補白名單，維護成本高過它抓到的東西。
- **建議**：不加進 pre-commit。如果還想要 Python 的死碼閘門，比較對準問題的做法是寫一支測試：把 OpenAPI 每個 `*Out` 欄位拿去比對 `web/src` 非測試檔的讀取（這次 C 區的做法）。但這是新規則，照全域規則要在測試檔內做雙向變異驗證，值不值得要另外評估，不在本票範圍。

## 附錄 A：工具輸出與誤報排除

所有檔案在 [`simplification-audit-2026-10-13/`](simplification-audit-2026-10-13/)：

| 檔案 | 內容 |
| --- | --- |
| `vulture_unused_anywhere.txt` | 159 條：掃描範圍含 `berth tests scripts`，仍判為沒人用 |
| `vulture_used_only_in_tests.txt` | 154 條：只掃 `berth` 的 313 條減掉上一份，也就是只有測試或腳本在用的 |
| `knip.txt` | `pnpm --dir web dlx knip@6.41.0 --no-progress --directory <web>` 的原始輸出（無設定檔） |
| `A-worker.md` … `D-worker.md` | 各區 worker 的報告；〈工具結果判定〉表逐條列出判定與理由（A 72 條、B 66 條、C 175 條、D 39 條） |
| `A-review.md` … `D-review.md` | opus 複核；〈工具判定抽查〉核對 worker 的判定 |
| `scripts/i18n_scan2.cjs` | i18n 掃描（參數是 `web/` 路徑）：用 TS 轉譯 `resources.ts` 取得實際的 key 樹，再用 AST 收字串字面量與樣板字串的開頭配對。結果 2085 個 key 裡 1523 個有字面量、562 個是動態前綴、未使用 0 |
| `scripts/i18n_dupval.cjs` | 找整句相同的 i18n 值（S2 的依據） |

兩支腳本都吃 `web/` 的路徑當參數（`node scripts/i18n_scan2.cjs <web 路徑>`），用 `web/node_modules/typescript` 轉譯 `resources.ts`，所以要先在 `web/` 裝好依賴。`i18n_scan2.cjs` 只讀 zh-Hant 那棵樹（zh-Hant 與 en 的 key 對稱另外比過），會把明細寫到當前目錄的 `i18n_out2.json`，並把所有樣板字串開頭印到 stdout；`i18n_dupval.cjs` 會略過短於 14 字的值。worker 與 review 提到的其他腳本（`i18n_scan3.cjs`、`i18n_scan4.cjs`、`testonly.cjs`，以及 Python 的探查腳本）都是一次性的，沒有保留。

**排除過程摘要**

- vulture 313 條，逐條歸成成立、刻意接縫或誤報，由 worker 用 grep 判定，每條一列。複核抽查了 B 14 條、A 18 條、C 20 條誤報加上 C 全部的成立條目，只抓到一條判錯：`models/setting.py:37` 的 `settings.updated_at` 原判誤報，其實是只寫不讀，已併入 S33。B 區有 `MediaInfoSummary` 的欄位在工具層級判成立，複核改判為刻意保留。
- knip 39 條，複核逐條核對全部成立；另外抽查了 worker 判為「只在測試用」的 8 個名稱，每個在 production 檔裡都有使用。
- i18n「0 未使用」的可信度是中等。寬前綴（例如 `interfaceLogin.`）底下的 key 一律算可能用到；動態後綴只用常見 token 驗證，驗證力弱。複核另外抽驗了 46 個 snake_case 動態 key，`jobs.event.*` 的 27 個對上 `EVENT_TYPES` 的 27 個成員、`jobs.plan.why.*` 的 51 個 code 都在 `berth/` 找得到，沒有發現反例。這屬於「沒找到反例」，不是證明。i18next 有型別設定，少了 key 會是 `tsc` 錯誤，但多出來的 key 抓不到。
