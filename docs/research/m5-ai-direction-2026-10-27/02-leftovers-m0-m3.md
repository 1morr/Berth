# M0–M3 票 Comments 遺留項審計（開 M5 前）

審計日期 2026-10-27；基準 `main` `5fc0bbc8`（v0.3.0 發布後）。唯讀審計，未改程式碼、票、docs。

範圍：`.scratch/m0`、`m1`、`m1.5`、`m2`、`m3` 底下全部 94 張票（M0 11、M1 23、M1.5 12、M2 18、M3 30）的 `## Comments` 段；五個里程碑的票都有這一段。

## 1. 摘要

| 範圍 | 總條數 | 後續票已處理 | 仍未處理 | 已不適用 | 與 M5 相關 |
| --- | --- | --- | --- | --- | --- |
| M0 / M1 / M1.5 | 133 | 76 | 46 | 11 | 10 |
| M2 | 95 | 28 | 62 | 5 | 15 |
| M3 | 189 | 25 | 134 | 30 | 26 |
| 合計 | 417 | 129 | 242 | 46 | 51 |

- 「條」是 Comments 裡一個獨立的未處理發現；Comments 已寫明「已修」「同 commit 處理」的不算。同一張票裡同類的純風格判斷題（Data Clumps、命名相近、重複兩行之類）有些被合併成一列，所以條數是下限。
- **仍未處理的 242 條裡，絕大多數是票上已結案的「判斷題」「刻意行為」「沒有 repro」**（M3 票 21 的歸類為主，約 90 條），沒有一條是已知的資料損壞或安全問題。真正有後果的集中在第 3 節。
- **驗證深度不一**：M0–M1.5 的判定我逐條對過 `berth/`、`web/src`、後續票；M2 的 95 條與 M3 的 189 條由兩個子代理各自逐票審，我抽查了 M5 相關的幾條（`review.py`、`rss.py`、`issues.py`、`test_command_marks.py`、`api/issues.py`）都與其說法相符。M3 的 UI 微項（票 06h、06i、21 的 P2/P3）有不少依據欄標「未重驗」，是靠票 21 的歸類或 plan 文字，不是我看過程式碼。
- **M4 票 107 與 M4 票 15 推翻了很多 M3 UI 項**：票 20（請求預算）整張被 107 推翻，06c / 06d / 06g 與 06h 的大半落在 M4 重做精靈的範圍，所以 M3 有 30 條「已不適用」。

## 2. M5 相關的現況（plan §11.6 點名的幾項）

### 2.1 `tests/unit/test_command_marks.py` 豁免表

- `BEFORE_M3` 現在有 **41 個模組**（`tests/unit/test_command_marks.py:31` 起；腳本解析 frozenset 得 41）。plan §11.6 寫的是 42，少一個，但表裡沒有任何一個模組被補完而移除；差一個的原因我沒追（`git log -S` 只找到建表的 `4b167c67`，之後沒有人從表中拿掉過名字，更可能是 plan 當時數錯）。
- 41 個模組：`auth bench claims clients complete deeplink deletion discover downloads duplicates events health health_issues hints importer inventory issues jellyfin jellyfin_access jellyfin_images jobs media plan plan_review plan_view qbittorrent reconcile reimport rematch resolve_schedule resolver routes search settings setup steps tmdb tracking watch watch_area watching`。其中 `deletion`、`rematch`、`reimport`、`duplicates`、`reconcile`、`claims`、`routes` 是 M2 才長出來的，所以「豁免」其實也涵蓋了 M2 新模組，不只 M3 之前就在的。
- M3 以後新增的 service 模組（`rss`、`oneshot`、`first_batch`、`ledger_rebuild`、`notify`、`waiting`、`weekly`、`sweep` 等）不在表內，已被守；`services/` 目前共約 60 個檔，`@command` 標記共 81 處。
- 閘門漏洞（M4 票 126 發現，不在 M0–M3 範圍但直接影響 M5）：`test_command_marks` 用 `inspect.iscoroutinefunction`，**包過 `@asynccontextmanager` 的公開函式不標也不紅**（`.scratch/m4/issues/126-downloading-notice.md`），閘門未修。

### 2.2 plan §11.6 點名的標記

| 項目 | 現況 | 位置 |
| --- | --- | --- |
| `confirm_audit` / `confirm_audits` 的反向命令 | 仍是 `inverse="review.undo_audit"`，語意對不上：`undo_audit` 拆掉入庫、整筆 Job 拉回 `review`，而且拒絕已確認的列（`not_audited`）。plan 要求另立「取消確認」或改 `inverse=None`，沒有任何票做 | `berth/services/review.py:347,365`；`undo_audit` 在 `:391` 只標 `REVERSIBLE` 無 inverse；`_back_to_review` `:459-479` |
| `services/issues` | 仍在豁免表。`count_open` 等三支 `READ` 已標（半標），**`resolve_issue` 未標**，各動作（重新鏈接、recheck、重新反查、忽略、刪 complete 等）要逐顆標等級 | `berth/services/issues.py:240-258`、`:319`；`IssueAction` 動作表 `:956` |
| `rss.poll_due` | 仍標 `Effect.REVERSIBLE`；它是背景迴圈入口，唯一呼叫端是 `berth/pipeline/rss.py:18`，登錄表會把它當 AI 工具 | `berth/services/rss.py:844-845` |
| `rss.delete_feed` | 仍標 `REVERSIBLE`、`inverse="rss.add_feed"`；它連帶 CASCADE 刪 Feed Item，Item 的 `error` 與 Feed 的 `interval_sec` 回不來 | `berth/services/rss.py:670-671` |
| M3 加進舊模組、改狀態卻沒標的四支 | 全部仍無 `@command`：`jellyfin.save_bundled_libraries`、`jobs.fail_interrupted`、`issues.close_settled`、`resolver.settle_verdicts` | `berth/services/jellyfin.py:237`、`jobs.py:1181`、`issues.py:400`、`resolver.py:356` |
| 「可逆但沒有單一反向命令」的已標命令 | `set_*exclusions`（三支）、`correct_series`、`confirm_series`、`correct_series_from_plan`、`subscribe_mikan`、`undo_audit`：標 `REVERSIBLE` 但 `inverse=None`。登錄表要先定「這類能不能給 AI 自動做」 | `berth/services/rss.py`、`series_review.py`、`review.py:391` |
| 命令簽名離 pydantic 輸入還有一段（plan §11.6 2026-09-26 更正） | 仍成立：命令吃 session / factory，拒絕是各模組自己的例外；`DeleteScope` 在 API 是四個 bool 參數（`berth/api/jobs.py:481-504`），`IssueResolveIn.media` 以空字串當哨兵（`berth/api/issues.py:175`），`api/routes.py` 五支端點共用九種理由聯集的 `REFUSAL_RESPONSES`（`:80`） | 見 M2 票 02a / 04 / 10 列 |
| `AiPlanner` | `berth/adapters/ai.py:23,40` 只有 Protocol 與 `NullAiPlanner`，**至今沒有呼叫端**（plan.md:326）；M1 票 07 原本留給 M4，brief §6.10（2026-09-24）改成 M5 第一種 AI 任務 | — |

## 3. 仍未處理條目，依嚴重度

判準：**擋** = 不處理就沒辦法拆 M5 的登錄表票或讓影子模式 / 自動模式安全；**須進票** = 不擋拆票，但 M5 對應的票必須把它列進驗收或前置，否則 AI 路徑會重現舊縫；**不擋** = 與 M5 無關。

### 3.1 擋（M5 開頭的登錄表票必須先處理或明說決定）

1. **豁免表 41 個模組都沒標，`services/issues.resolve_issue` 未標**（M3 票 05、17；M2 票 05、09、10）。登錄表「AI 的工具只從這裡來」，沒標的命令等於不存在；Issue 動作是 M6 的主體、「忽略 Issue」在 plan 是 Proposal。拆票時要決定逐模組補的順序，並同時處理 `jellyfin` / `jobs` / `issues` / `resolver` 四支改狀態卻沒標的命令與 `asynccontextmanager` 閘門漏洞。
2. **`confirm_audit(s)` 的 `inverse=review.undo_audit` 語意錯**（M3 票 05；M2 票 06）。AI 任務「audit 的確認或撤銷」直接用這一對：若按 inverse 撤銷一次確認，實際會拆掉入庫並把 Job 拉回 review。要在登錄表前決定另立「取消確認」或 `inverse=None`。
3. **`rss.poll_due` 標 `REVERSIBLE`、`rss.delete_feed` 標可逆**（M3 票 08）。前者會被登錄表當成 AI 工具、後者標錯等於放行一個其實回不來的刪除（Feed Item、`error`、`interval_sec` 不可還原）。改標與否是登錄表契約，不能留到影子模式之後。
4. **「可逆但無單一反向」沒有規則**（M3 票 10、13、14b、19；M2 票 06）。至少七支命令是這個形狀；M5 驗收「AI 不能在沒人確認下執行 `irreversible`」的邊界取決於登錄表怎麼對待它們，需要一條明確規則（例如：可逆但無 inverse = 允許自動但不給「逐筆撤銷」？還是視為需 Proposal？）。AI 活動頁的「逐筆撤銷」也依賴它。
5. **核准被擋的列、`held_proposal` 不再比帳本**（M3 票 14、14b）。M5 驗證要求「不撞目標路徑、季集範圍」，AI 的結果走同一條核准路徑，會踩到重複版本與 `span_clash` 漏檢。不修，AI 的驗證關卡有一個已知的洞。

### 3.2 須進票（不擋拆票，但對應 M5 票要列進前置或驗收）

6. **沒有 `job_hash` 的帳本列確認 / 撤銷不寫 Event**（M2 票 06；`berth/services/review.py:415-419`）。M5 驗收要求每次呼叫記 Event；AI 動這類列沒有落點。
7. **`undo_audit` 把整筆 Job 拉回 review、`summary_json` 沒重算**（M2 票 06、07；`review.py:459-479`）。逐筆撤銷 AI 的 audit 決定時，副作用範圍要在登錄表說清楚。
8. **`QUEUE_LIMIT`=200 截斷時整組確認把 Series 標成確認過；逐列確認不標 Series**（M3 票 13；`berth/services/review.py:85`）。AI 批次確認若走同一支命令會重現。
9. **`resubmit_job` 不看磁碟門檻**（M3 票 04；`berth/services/jobs.py:649` 對 `:397,:495`）。M6 若讓 AI 自動重新送單會繞過。
10. **actor 約定**：`downloads.SYSTEM`、`rss.SYSTEM = actor_of(None)`、`jobs.actor_of` 多份寫法（M3 票 02、09；M2 票 10 `ledger_rebuild.py:40`）。`jobs.py:1315` docstring 已預告 `ai` actor，加進去前要先收斂。
11. **`_replace_with_link` 沒有 `job_lock`**（M2 票 09；`berth/services/issues.py:548-580` 附近，我未見 `job_lock` 呼叫）。AI 與人同時按同一件 Issue 的競態。
12. **`issues.detail_json.action` 一鍵兩義**（M2 票 09）：偵測時是 `PlanAction`，resolve 時被覆寫成按了哪一顆。「忽略 Issue」做成 Proposal 時會讀到。
13. **拒絕理由三組 enum 的畫面對照沒有閘門**（M2 票 02）：`Partial<Record<RouteRefusal, string>>`（`web/src/settings/AddRoute.tsx:26`、`setup/buildRefusal.ts:13`）；登錄表要登錄「拒絕理由」時，新增理由沒有任何東西逼人補畫面文案。
14. **`AiPlanner` 無呼叫端**（M1 票 07）與 **`job_files.release_info_json` 不填**（M1 票 11）：影子模式比對「規則層 vs AI」若要逐檔，需要後者。
15. **`jellyfin_item_resolved` 事件只帶 `count`、事件去重靠「最近一分鐘同型別」**（M1 票 12）：AI 活動頁逐筆撤銷 / 追溯要事件帶 id 時會碰到。
16. **`mark_played(played=False)` 布林旗標**（M1.5 票 05）：標反向命令時，反向是同命令另一個參數而不是另一支函式；`inverse` 字串指名函式會對不上，要先拆或明說。
17. **`_missing()` 捏造 `tmdb_id=0`**（M1 票 04；`berth/services/media.py:410`）：M7 MCP 包這個回應時給假值；原票就寫「有 API 消費者時再定」。
18. **規則層 low 的觸發量相關**：票 16 的發佈時間推測偏離使用者尚未追認（`docs/plan.md:965`、progress.md 2026-09-26），票 14 / 15 的已知盲點（網路先行配信、與正片同長的番外、TMDB `runtime` 為 `null` 約 46.6%）。這些決定規則層漏多少給 AI、以及「三道程式檢查標出的可疑入庫」這個任務型別的輸入量。
19. **`correct_series` 的 `Part N` offset 可能多算**（M3 票 13）：AI「季號與 offset 修正」任務的驗證要覆蓋。

### 3.3 不擋（與 M5 無關，按嚴重度由高到低）

- **使用者影響**：M3 票 11 `prime_feed(later)` 與背景 poller 寫同一批 guid 撞 `(feed_id, guid)` unique 冒 500（`berth/services/rss.py:1052-1100` 仍是 `session.add` + `flush`，無 `ON CONFLICT`）；M3 票 10 `_rescreen` 讀後寫會把剛送出的 Item 改回 `excluded`（`rss.py:1623-1640`）；M3 票 02 `client_error` 與 `missingFiles` 互不接回（`downloads.py:410-412`）；M3 票 11 預覽沒叫 `_sent_before`；M3 票 01 第二個刪除請求的 CAS（無 `expected_state`）。皆無 repro，票 21 歸「不做」。
- **功能缺口**：M0 票 11 十個索引站預設全勾（待決，brief §19 無對應列）；M1 票 08 TMDB 別名順序隨機佔掉查詢名額、同名不同作品通過粗篩（`search.py:466`）；M1 票 11 resolution 不採 mediainfo（`naming/__init__.py:453`）；M1 票 07 `.default` 字幕旗標；M3 票 15 每集短於 5 分鐘的短篇動畫被降成 extra（`classify.py:80`）；M3 票 06b 精靈後改 qBittorrent port 不會跟著走（`qbittorrent.py:468-476`，已寫進 troubleshooting）。
- **無障礙 / 效能**：M3 票 06 / 21 的 898 KB 單一 chunk、無路由拆分；觸控目標 24px；h5 跳號（`QbittorrentStep.tsx:234`）；同名控制項。
- **程式碼風格判斷題**：其餘 M1.5、M2、M3 的 Data Clumps、命名相近、重複兩份、`match kind` 散在三處等（`berth/services/rss.py:1009,1122,2579`）；都已在票內寫明理由，無新證據推翻。

## 4. 全表

判定欄：**後續票已處理** 一律附後續票號並已對現況程式碼確認；**仍未處理** 附現況位置；**已不適用** 附推翻它的票號或決定列。「M2 票 NN」「M3 票 NN」是被審計的票，「M4 票 NN」等是處理它的後續票。

### 4.1 M0 / M1 / M1.5

| 來源 | 發現 | 判定 | 依據 | 與 M5 相關？ |
| --- | --- | --- | --- | --- |
| M0 票 01 | GitHub Actions 在 PR 上跑完全部檢查「未驗證」（當時沒有 remote） | 後續票已處理 | M0 票 03（remote `1morr/Berth` 建好、`v0.1.0-rc1` release workflow 綠）；M1 票 15（nightly e2e）；`git tag` 已到 v0.3.0 | 否 |
| M0 票 01 | 型別感知 eslint（`recommendedTypeChecked`）暫未啟用 | 後續票已處理（部分） | M0 票 11 只開 `no-floating-promises` 與 `no-misused-promises`（`web/eslint.config.js:49-50`，檔內註解說明不開整包的理由）；整包仍未開，屬有意 | 否 |
| M0 票 02 | 前端型別手寫、`apiGet` 用 `as T`，要接 `openapi-typescript` 並讓 CI 檢查過期 | 後續票已處理 | M1 票 02（`pnpm gen:api`、CI `api-types` job，`.github/workflows/ci.yml:106`）；M2 票 02（拒絕理由四組改由 OpenAPI 產） | 否 |
| M0 票 02 | 結構化日誌每行帶 job id | 後續票已處理 | M1 票 09（`berth/logs.py` 的 `ContextVar`）；plan §11.2 T1.9 | 否 |
| M0 票 02 | `settings.services.*` 缺「最後健康狀態」 | 後續票已處理 | M0 票 10（健康迴圈、`GET /api/health/detail`） | 否 |
| M0 票 05 | `DESIGN.md` 尚未產生 | 後續票已處理 | M0 票 11（`/impeccable document` 產出） | 否 |
| M0 票 05 | shadcn/ui 未引入，等出現 dialog / popover / combobox 再引入 | 已不適用 | `web/package.json` 沒有 shadcn、`web/src/components/` 無 `ui/`；後續元件自建（`controls.tsx`、就地確認），DESIGN.md 的設計語言與 shadcn 不並存 | 否 |
| M0 票 05 | CSRF 伺服器端檢查留給票 07 | 後續票已處理 | M0 票 07（缺 `X-Requested-With` 的 POST 回 403，票內實測） | 否 |
| M0 票 06 | `SetupStep` / `StepView` / `StepOut` 三個同形型別 | 仍未處理（有意，import-linter 層級要求） | 票內已說明；`api → models` 被 `lint-imports` 擋，沒有推翻它的後續票 | 否 |
| M0 票 07 | 帳號長度無上限（shape brief §5 寫 1–255） | 仍未處理（有意） | `berth/api/auth.py` 的 `LoginIn` 沒有 `max_length`；理由是 Jellyfin 自己會拒 | 否 |
| M0 票 07 | `routes.tsx` 的 `isSetupComplete → requireSession` 重複兩行 | 後續票已處理 | M0 票 11（收成 `requireSignedInPage`）；M2 票 03 又抽 `requireAdminPage` | 否 |
| M0 票 09 | `read_route_status` 以媒體庫名索引，同庫多 Route 在畫面收斂成一條 | 後續票已處理 | M1 票 14（Route 設定頁「一庫多條」，`/settings/routes`）；plan §11.2 T1.9 | 否 |
| M0 票 09 | 重跑第 7 步會刪掉沒被勾到的 Route（M1 有 Job 後要改） | 後續票已處理 | M1 票 14（精靈只新增不改不刪，明確刪除動作）、M1 票 14a（刪除前的用量檢查） | 否 |
| M0 票 10 | 健康檢查缺「媒體庫掛 TVDB 插件」警告 | 後續票已處理 | M2 票 09c；`berth/domain/enums.py:252` `IssueType.LIBRARY_USES_TVDB` | 是（`IssueType` 是 M6 Issue 變 AI 任務的輸入） |
| M0 票 10 | 磁碟空間沒有門檻判定 | 後續票已處理 | M2 票 09c / M3 票 04；`berth/domain/enums.py:255` `LOW_DISK_SPACE`、`DiskSettings.min_free_gb` | 否 |
| M0 票 10 | `ServiceHealth` 同形狀寫四層（含 TS） | 後續票已處理（TS 那層） | M1 票 02 改用產出型別；前三層是 import-linter 要求，有意保留 | 否 |
| M0 票 10 | `GET /api/settings/services` 回整份 `HealthDetail`（含 `routes`），設定頁用不到 | 仍未處理（有意，等第三個消費者） | M1 之後沒有後續票動它；`berth/api/settings.py` 沒有拆 | 否 |
| M0 票 11 | 密碼只有一格、無二次確認欄（產品立場，待使用者決定） | 後續票已處理 | M4 票 06（`ef382368`，2026-09-28）：`web/src/setup/OwnerStep.tsx:229,258,341` 有 confirm 欄與 mismatch 判斷 | 否 |
| M0 票 11 | 十個索引站預設全勾（產品立場，待使用者決定） | 仍未處理（待決，未見決定列） | 我在 brief §19 沒找到對應決定列；M3 票 06e 把勾選清單改成「每站語言名與說明」，但預設勾選規則沒被明說改過 | 否 |
| M0 票 11 | 綠 / 紅等重；全綠健康頁 1000px、綠章重複八次 | 後續票已處理 | M2 票 03 第 16 條（`UNPAINTED_FILL`，常態不塗漆） | 否 |
| M0 票 11 | 亮色主題 surface 文件與程式碼互相矛盾 | 後續票已處理（待確認） | M2 票 03 第 11 條收掉 DESIGN.md 三處與 Known contradictions 的語言鍵那條；亮色信號色那條沒在 M2 票 03 逐字點名，列「拿不準」 | 否 |
| M0 票 11 | `assigned` 黃有三個意思 | 後續票已處理 | M2 票 03 第 11 條（語言鍵選中態改 `deck`+`ink`）；checkbox accent 與主要按鈕是否也改了未逐一驗，列「拿不準」 | 否 |
| M0 票 11 | 三頁缺 `<h1>`、無 nav landmark、skip link、精靈 h3 在 h2 前 | 後續票已處理 | M2 票 03 第 13 條（`PAGE_TITLE` 一份、三頁補 `<h1>`）；M1 票 15 audit 加 skip link（票 15 Comments「skip link 浮出時 90×35px」） | 否 |
| M0 票 11 | 非 admin 開 `/settings/services` 靜默彈回 | 後續票已處理 | M2 票 03 第 14 條（`?denied=true` 與健康頁說明） | 否 |
| M0 票 11 | `<summary>` 在無障礙樹是 `generic` | 已不適用（查證後不改） | M2 票 13 第 8 條：ARIA in HTML 規定 `summary` 不得指定 role，不修 | 否 |
| M0 票 11 | 窄版 Route 列把路徑尾巴截掉 | 後續票已處理 | M2 票 03 第 15 條（`truncate` → `wrap-anywhere`） | 否 |
| M0 票 11 | 每一步左欄剖面與右欄纜繩列兩份實作（重構） | 仍未處理 | M2 票 03 第 17 條標「可延」未做，M2 票 16 延後；plan §11.3 D 組「不排里程碑」 | 否 |
| M0 票 11 | `v0.1.0` 沒有 tag，compose 範本 pin `:latest` 為空 | 已不適用 | `git tag` 已有 v0.2.6–v0.3.0，已正式發版 | 否 |
| M0 票 03 | `BERTH_IP`、`BERTH_QBITTORRENT_CONF` 沒寫進 `deploy/.env.example` | 仍未處理（有意） | `deploy/.env.example` 仍不含這兩個名字（grep 空）；一個是 compose 錨點、一個是測試 seam | 否 |
| M0 票 04 | 版本標籤含中文（group token 保留字幕組原文）沒測到 | 仍未處理 | brief §20.1「多版本」保留「未證實」（progress.md 2026-09-07 票 04 條）；Jellyfin 12 原生合併後（M1 票 14b）改讀 `MediaSources[].Name`，M1 票 15 真環境只驗了 ASCII tag | 否 |
| M0 票 04 | 原生 Linux 宿主與 NAS 的硬鏈接未測（brief §20.6 兩條保留） | 仍未處理（部分） | M0 票 11 / M1 票 15 仍是 Docker Desktop VM；CI e2e（M1 票 15）在 GitHub runner 的原生 Linux ext4 上跑硬鏈接 stat 同 inode，等於原生 Linux 已覆蓋，NAS 未測 | 否 |
| M0 票 08 | `QbittorrentCategory` / `pause_parameter` 只有契約測試在用 | 後續票已處理 | M0 票 09（category）、M1 票 09 / 10（送單與 poller） | 否 |
| M0 票 08 | 既有 Prowlarr 的「測試」不檢查有哪些站 | 後續票已處理 | M3 票 06e（加入之後試搜，`indexer.search_indexers`，progress.md 2026-09-25 條） | 否 |
| M1 票 01 | 研究未量到的部分：Mikan 無 2013 年前番、nyaa.si 被 DNS 攔截、9,392 集捨棄 | 仍未處理（研究限制） | `docs/research/anime-episode-source.md` §8；後來 M1 票 14d 補了 28→32 筆語料，但英文字幕組仍無樣本 | 否 |
| M1 票 02b | 通過 TMDB 閘門後 BTH 3 的詳情列不動 | 已不適用 | M2 票 03 第 4 條先修；M3 票 06e 把泊位板拆成五格（BTH 4 索引站、BTH 5 TMDB） | 否 |
| M1 票 02b | 憑證是明文欄位（TMDB / 索引站 API key 三處一起改） | 後續票已處理 | M2 票 03 第 12 條；`web/src/setup/TmdbStep.tsx`、`JellyfinExisting.tsx` 使用 `PasswordField` | 否 |
| M1 票 02b | `complete.failed` 在缺憑證時錯怪後端 | 後續票已處理 | M2 票 03 第 5 條（`complete.unfinished`） | 否 |
| M1 票 02b | `api.themoviedb.org` 被擋的使用者走不完精靈（待確認是否為想要的產品） | 後續票已處理（已拍板接受） | brief §19 第 757 列（2026-09-17）：接受 | 否 |
| M1 票 02b | 失敗時多給的連線探測指令（REACHABILITY_PROBE）外溢 | 仍未處理（有意保留） | 票內判為保留，未被推翻 | 否 |
| M1 票 03 | 卡片不是連結 / 追蹤動作在票 04 / `media` 四欄無消費者 | 後續票已處理 | M1 票 04、04b、09（凍結 `folder_name`） | 否 |
| M1 票 03 | `{tv,movie}/popular` 沒有分頁，一個 feed 固定 40 格 | 仍未處理（plan 未要求） | 沒有後續票提到無限捲動 | 否 |
| M1 票 03 | `include_adult=false` 寫死 | 仍未處理（有意） | `berth/adapters/tmdb/client.py:69` | 否 |
| M1 票 02 | `LoginIn.username/password` 在產出型別是選填 | 仍未處理（有意） | `berth/api/auth.py:27-31` docstring 說明 | 否 |
| M1 票 02 | CI `api-types` job 與 `backend`/`web` 重複 checkout 與安裝 | 仍未處理（有意） | `.github/workflows/ci.yml:106` 仍是獨立 job | 否 |
| M1 票 04 | `_missing()` 為認不得的 id 捏造 `tmdb_id=0` / `kind=tv`；留給 MCP 消費者時再定 | 仍未處理 | `berth/services/media.py:410` `tmdb_id=0` | 是（M7 MCP / M5 登錄表輸出若包這個回應會拿到假值） |
| M1 票 04 | 一部四季作品序列打 7 支 TMDB、1213 集季表無分頁 | 後續票已處理（季表）／仍未處理（序列） | 季表：M1.5 票 09（收起不渲染、長清單）；序列請求沒有後續票併發化，24h 一次快照，低 | 否 |
| M1 票 04 | 本票的追蹤 / 凍結 / `tracked` 判斷 | 已不適用 | M1 票 04b 推翻（brief §4.5 改寫、`media.tracked` 移除） | 否 |
| M1 票 04b | 動作列不黏底、`default_route_id` 退出 `MediaOut`、不做 watchlist | 已不適用（當時的偏離，後來被取代） | M1 票 08 / 09 把動作列與 Route 選擇接回；無 watchlist 為有意 | 否 |
| M1 票 05 | 特典對 TMDB season 0 只靠編號 | 後續票已處理（明說決定） | M1 票 06 決定 3（不靠集名 / 片長，最多 medium），語料 README | 否 |
| M1 票 05 | 語料缺 `sample` 檔與多集檔；`profile`/`min_confidence` 沒人讀 | 後續票已處理（多集檔、min_confidence）／仍未處理（sample） | M1 票 06（語料補單檔多集；`min_confidence` 接上）；`sample` 仍只有單元測試（票 06 自述） | 否 |
| M1 票 06 | 以發佈時間推測虛擬季（brief §6.4）刻意沒做，等票 08 接 `published_at` | 後續票已處理 | M1 票 14d / 14c（絕對編號證據規則，`berth/parser/mapping.py:557-559` 用 `context.published_at`） | 否 |
| M1 票 06 | `title.match_media` 候選池只有 `ParseContext.candidates`，由 M3 RSS 餵 TMDB 結果 | 後續票已處理 | M3 RSS 系列（票 13 起 `rss-series-by-work`）；`berth/parser/binding.py` | 否 |
| M1 票 07 | 與帳本既有版本重複 → `duplicate`（要等帳本） | 後續票已處理 | M2 票 08；`berth/domain/enums.py:175,178` `DUPLICATE_SKIPPED` / `DUPLICATE_DECIDED`；`berth/services/duplicates.py` | 否 |
| M1 票 07 | 凍結 `folder_name` 與快照分歧，換來源只動 `folder_name()` / `_series_prefix()` | 後續票已處理 | M1 票 15（修掉「凍結資料夾名沒被 planning 讀」）；`berth/naming/__init__.py:64-72` 先讀 `media.folder_name` | 否 |
| M1 票 07 | `.default` 字幕旗標：位置定了，M1 沒有東西決定預設軌 | 仍未處理 | `berth/naming` 沒有產生 `.default.` 的程式碼（grep 空）；沒有字幕語言偏好設定票 | 否 |
| M1 票 07 | `AiPlanner` 實作留給 M4（plan §4.5） | 仍未處理，改派 M5 | `berth/adapters/ai.py:23,40` 只有 Protocol 與 `NullAiPlanner`，至今沒有呼叫端（plan.md:326）；brief §6.10（2026-09-24）改成 M5 第一種 AI 任務 | 是（M5 第一批任務型別「規則層 low 的 Plan」直接吃它） |
| M1 票 08 | `Season 3 / … Season 3 - 46` 被 `_LOOSE_RANGE` 讀成 `S03E03–E46` | 後續票已處理 | M2 票 01；`berth/parser/release.py:66-89` 註解與規則 | 否 |
| M1 票 08 | TMDB 別名順序隨機，查詢上限五個 | 仍未處理 | `berth/services/search_queries.py:25` `MAX_QUERIES = 10`（M4 票 84 已改查詢預算與季記號，但別名「哪些語言值得問」的規則沒有票）——拿不準，標待確認 | 否 |
| M1 票 08 | 同名不同作品通過粗篩（`mentions()` 純字串包含） | 仍未處理 | `berth/services/search.py:466` 仍是 `mentions(result.title, snapshot)` | 否 |
| M1 票 08 | 窄版五條纜繩把結果表推到第二屏 | 後續票已處理 | M1.5 票 08（搜尋結束後五條纜繩收成一行摘要 287→44 px） | 否 |
| M1 票 08 | 兩個實作各一份 Fake → 一份共用 `FakeIndexerSearch`；Torznab client | 已不適用 | M4 票 37 移除 Torznab client（plan §11.2 T1.2） | 否 |
| M1 票 09 | `DELETE /jobs/{hash}`、`replan`、`reimport` 沒做 | 後續票已處理 | M2 票 04（刪除範圍）、M2 票 10（reimport）；`berth/services/deletion.py`、`reimport.py` | 是（`delete_job` 是 irreversible 命令的典型） |
| M1 票 09 | 送單失敗列停在 `submit_failed` 直到有人按重試，沒有自動重試 | 仍未處理（有意，plan §3.1） | 沒有後續票加自動重試；plan §3.1 寫的就是手動 | 是（M6 `submit_failed` 若變 AI 任務） |
| M1 票 09 | 進度 / 大小永遠 `—`；`job_files` 只建表 | 後續票已處理 | M1 票 10（poller 寫 `torrents/info` 與 `job_files`） | 否 |
| M1 票 10 | `issues` 表留給 M2（M1 只有 `issue_detected` 事件） | 後續票已處理 | M2 票 05 | 是 |
| M1 票 10 | pre-plan 後半（`plans` 表）到票 11 | 後續票已處理 | M1 票 11 | 否 |
| M1 票 10 | 同一新使用者兩次登入同時進來，`users.jellyfin_user_id` unique 讓其中一次 500 | 後續票已處理 | M2 票 01；`berth/services/auth.py:216-218` 接 `IntegrityError` | 否 |
| M1 票 10 | Windows 上 `poll` 情境留下 `C:\downloads`；11 個測試因 WSL bash 失敗 | 已不適用 | 開發環境現為 macOS；M1 票 15 修了「PowerShell 下 `deploy/` 腳本測試全紅」 | 否 |
| M1 票 11 | `unmatched` 不擋自動入庫（plan §3.1 已回寫） | 後續票已處理（為決定，非缺陷） | 已寫進 plan；M2 票 08 提供指派 | 否 |
| M1 票 11 | Plan item 理由是英文句子、不走 i18n（要改成 code + 參數） | 後續票已處理 | M2 票 07（`reason_code`；`berth/parser/planner.py`、`subtitles.py`、`runtime.py` 有 code）；`tests/unit/test_reason_codes` | 是（AI 的理由 / 影子模式比對需要封閉集合） |
| M1 票 11 | `job_files.release_info_json` 不填 | 仍未處理 | 沒有後續票提到；M1 沒有讀取者 | 是（M5 影子模式要比對「規則層 vs AI」逐檔解析時可能需要） |
| M1 票 11 | brief §6.8「resolution 以 mediainfo 為優先」未接上 | 仍未處理 | `berth/naming/__init__.py:453` 只從 token 辨識 resolution；`berth/parser`、`naming`、`services/plan.py` 都沒用 mediainfo 的 height | 否 |
| M1 票 11 | `list_jobs` N+1 多一支 | 後續票已處理 | M2 票 01 第 3 條（`_related` 有上限 `in_()` 批次，`services/jobs.py` 約 L835） | 否 |
| M1 票 11 / 13 / 14 | `.impeccable/design.json` 比 `DESIGN.md` 舊（hook 提醒） | 後續票已處理（但再度漂移） | M2 票 13 第 18 項做 `/impeccable document`；M2 票 16 又記「第四次、沒有閘門」→ plan §11.3 D 組不排里程碑 | 否 |
| M1 票 12 | MergeVersions 在反查成功後觸發 / 帳本 `jellyfin_item_id` 合併後可能不是主條目 | 後續票已處理 | M1 票 14b 移除 MergeVersions（Jellyfin 12 原生合併）；M2 票 09 `resolver.refresh_resolved` 換掉不再是主條目的 id | 否 |
| M1 票 12 | `/Items` 帶整份 `MediaSources` 在大媒體庫很重 | 後續票已處理 | M2 票 11 量測（`docs/research/large-library.md`）：瓶頸是 `inventory._survey` 二次方，不是 Jellyfin 回太多，不做分段取 | 否 |
| M1 票 12 | 事件去重查最近一分鐘同型別事件，無 payload hash；`jellyfin_item_resolved` 只帶 `count` | 仍未處理 | 無後續票；brief §5.2 寫 `(item_id)` 與實作不同 | 是（M5 AI 活動 / 時間線逐筆撤銷需要事件帶 id 時會碰到） |
| M1 票 12 | 沒找到兩次以上跑「重新掃描媒體庫」任務，大媒體庫代價 | 後續票已處理（量測） | M2 票 11 對帳一輪 27–31 s，未超門檻 | 否 |
| M1 票 13 | 深連結不帶 `serverId` 只在 12.0.0 驗過 | 已不適用 | M1 票 14b：只支援 Jellyfin 12 以上（plan T1.10） | 否 |
| M1 票 13 | 票 13 之前反查完的劇集沒有 `jellyfin_series_id`，卡片一直說「還在掃描」 | 後續票已處理 | M2 票 09（`resolver.refresh_resolved` 補 Series id） | 否 |
| M1 票 13 | 沒有 Issue 篩選；牆的篩選 UI 留 M2 | 後續票已處理 | M2 票 05 `/issues` 頁；M2 票 13 / 14 | 否 |
| M1 票 13 | `MediaTile` `·` 沒 `aria-hidden`、`MediaWall` 筆數 `aria-label` 掛 `<p>` | 後續票已處理 | M1 票 15 audit（見 progress.md）；M2 票 13（重複控制項名稱、清單語意） | 否 |
| M1 票 13 | 後端 `presence_of` / `_file_presence`、前後端 `jobState` 狀態分類各一份、三欄 Data Clumps、空狀態類名重複三次 | 仍未處理（判斷題，有意） | 票 13 Comments 與 M1.5 票 11 皆維持原判；`berth/services/inventory.py`、`web/src/jobs/jobState.ts` | 否 |
| M1 票 14 | `create_route` 與精靈 `_plan` 驗證沒合併；`api/routes.py` 五個重複 try/except；`routeRefusalOf` 與 `refusalOf` 重複；英文 `Library paths` 與 CONTEXT.md 落差 | 後續票已處理（refusal 重複、EN 分頁名）／仍未處理（其餘判斷題） | M2 票 02（`api/refusal.ts` 一份）；M2 票 03 第 8 條改子分頁 `Routes`，但 EN 頁標題 `Library paths` 留給下一張碰設定頁文案的票（M2 票 03 合併後補記） | 否 |
| M1 票 14 | 待使用者確認：精靈跑完前 `/api/routes` 匿名開放 | 後續票已處理 | M1 票 14a（門禁收緊，2026-09-15 拍板） | 否 |
| M1 票 14 | 刪除不清 qBittorrent 分類與 complete 子目錄 | 仍未處理（有意） | 沒有後續票；`berth/services/routes.py` 刪除路徑不碰 qBittorrent | 否 |
| M1 票 14a | 精靈勾選表標出已被佔用的路徑 | 後續票已處理 | M2 票 03 第 6 條 | 否 |
| M1 票 14a | `check_routes` 途中 Route 被刪仍是 `StaleDataError`，`POST /api/setup/routes` 500 | 後續票已處理 | M2 票 01；`berth/services/routes.py:693-698` | 否 |
| M1 票 14a | `_usage_of` 與 `_usages` 兩份計數；`api/setup.py` import `api/routes.py`；`_TAKE_WRITE_LOCK` raw SQL | 仍未處理（判斷題） | 票內說明；無後續票 | 否 |
| M1 票 14b | 同一集第二版本入庫後 Jellyfin 改兩個來源的名字，舊那筆停在舊名 | 後續票已處理 | M2 票 09（重新反查既有帳本） | 否 |
| M1 票 14d | 規則 2 差一天不觸發、無容忍；TMDB 沒有播出日也送審核 | 仍未處理（有意） | progress.md 偏差與決定；`berth/parser/mapping.py:557` 周邊 | 否 |
| M1 票 14d | 無職轉生 / Re:Zero `S2][02]` 會自動入錯（季號 = 方括號集號） | 後續票已處理 | M1 票 14f（`_SEASON_WORD_BEFORE_BRACKET`） | 否 |
| M1 票 14e | `services/search._context` 把作品類型填進 `ParseContext.route_collection_type`，搜尋不帶 Route 後名字不準 | 仍未處理（判斷題） | 票內判斷：domain 欄位名，不改 | 否 |
| M1 票 14e | 精靈泊位 4 剖面「Route 數」建完後變 0 | 後續票已處理 | M1 票 15 code-review 帶出、已修（票 15 Comments「兩條由 code-review 帶出、已修」） | 否 |
| M1 票 14f | `_SEASON_WORD_BEFORE_BRACKET` 與 `_BRACKET_EPISODE` 片段相同未抽 | 仍未處理（量太小） | 票內判斷 | 否 |
| M1 票 15 | e2e 的 nightly 排程在 session 結束前沒輪過 | 後續票已處理 | M1.5 票 11 與 M2 / M3 / M4 票 133（CI e2e 紀錄），nightly 已持續跑 | 否 |
| M1 票 15 | 兩個 commit body 一行 73–74 字元（已 push） | 仍未處理（不可逆） | 已 push，改寫要 force push；已發版到 v0.3.0 | 否 |
| M1 票 15 | fake `inventory` 情境把 demo torrent 網址寫死成 8484 | 仍未處理 | `scripts/fake_setup_server.py:198` `DEMO_PORT = 8484` | 否 |
| M1 票 15 | critique 其餘小項、詳情頁版面沒有上限 | 後續票已處理 | M1.5 票 08–10（shape 重做詳情頁、長清單）；M2 票 13 / 14 | 否 |
| M1 票 15 | TMDB 連不上就走不完精靈、顯示用標題語言（兩條產品問題，brief §19 待決） | 後續票已處理 | brief §19（2026-09-17）：前者接受，後者 M1.5 票 02 | 否 |
| M1.5 票 01 | 實驗腳本形狀重複（`Credential.header` 等）、`Row.expected` 混放 | 仍未處理（判斷題，一次性腳本） | `scripts/experiments/`；票內與 M1.5 票 11 皆維持原判 | 否 |
| M1.5 票 01 | `useritems-resume.restricted.json`、`shows-nextup.restricted.json` 沒有測試引用 | 後續票已處理 | 檔案已不在 `tests/fixtures/http/jellyfin/`（只剩 `.watching` / `.series` 系列），grep 無引用 | 否 |
| M1.5 票 02 | 媒體庫牆排序仍照 `zh-TW` 標題 | 後續票已處理 | M1.5 票 03（牆的排序改由 Jellyfin 提供）、票 06 | 否 |
| M1.5 票 02 | EN 介面海報仍取 `zh-TW` 那一輪 | 後續票已處理 | M1.5 票 11（`poster_url` / `poster_url_en`，`berth/services/media.py:102`） | 否 |
| M1.5 票 02 | `JobOut.media_title` 改了語意沒改名；`title`/`title_en` 成對出現在九個型別 | 仍未處理（判斷題） | `berth/services/jobs.py:271-281`；M1.5 票 11 維持原判，且 `poster_url`/`poster_url_en` 為持久化與 wire 格式，破壞性變更要先問 | 否 |
| M1.5 票 02 | `services/media._fetch` 的 `display.title or base.title` 走不到、沒測試 | 仍未處理 | M1.5 票 11 列為「維持原判」 | 否 |
| M1.5 票 03 | 單一作品與集的讀取跟著第一個呼叫端加進 `jellyfin_access` | 後續票已處理 | M1.5 票 05、08（M1.5 票 11 確認） | 否 |
| M1.5 票 03 | `sortBy=SortName` 證明不了有作用；其他排序鍵票 06 | 後續票已處理 | M1.5 票 06（契約測試直接比對 `CommunityRating` / `LastPlayedDate` / `ProductionYear`） | 否 |
| M1.5 票 03 | 被刪掉的 Jellyfin 帳號沒實測 | 後續票已處理 | M2 票 11（`docs/research/large-library.md:137-152`：刪除的帳號每一支都是 404，`user_policy` 404 → `NotFoundError`） | 否 |
| M1.5 票 03 | `library_index` 每次看牆都整份抓、沒快取 | 後續票已處理（量測後決定不做） | M2 票 11：inventory p95 3.4 s → 修 `_survey` 二次方後 0.66–0.68 s，plan §11.3 決定 2：不做快取 | 否 |
| M1.5 票 03 | 兩端點同形 try、`PAGE_KEY` 沒用 `GHOST_LINK`、`library_page` 先帶 `fields` | 仍未處理（判斷題） | M1.5 票 11 維持原判 | 否 |
| M1.5 票 04 | `PosterSlot` 是第三份海報元件；`image_url` 寫死 `/api/jellyfin/...`；`/jellyfin` 前綴分在兩個 router | 後續票已處理（海報元件）／仍未處理（其餘判斷題） | M2 票 13（`Poster.tsx` 與 `ArtSlot` 合併）；其餘無後續票 | 否 |
| M1.5 票 04 | 「Jellyfin 連不上」圖片只有兩層測試，沒有瀏覽器實跑 | 後續票已處理 | M1.5 票 11 e2e 最後一條停掉 Jellyfin 容器再起回來 | 否 |
| M1.5 票 05 | 標為已看不確認，會把「看到一半」位置歸零；副作用沒人拍板 | 後續票已處理 | M1.5 票 08（shape 使用者拍板：看到一半的項目標為已看先確認，牆一起改） | 否 |
| M1.5 票 05 | 「待審」「Unmatched」篩選後卡片 `watch` 是 `null` | 仍未處理（有意，代價經 M2 票 11 量過） | `berth/services/inventory.py:652` `watch=None`；M2 票 13 把這類篩選改成一列一件事清單 | 否 |
| M1.5 票 05 | 寫入失敗訊息與 401 送回登入頁只有 vitest | 仍未處理 | M1.5 票 11 列為「維持原判」，e2e 走 API 層 | 否 |
| M1.5 票 05 | `api/jellyfin.py` Divergent Change、`mark_played(played=False)` 布林旗標、`libraryId` 穿過 `WatchToggle` | 仍未處理（判斷題） | 同上 | 是（M5 命令登錄表要為 `mark_played` 標 `@command` 與反向命令時，布林旗標會讓「反向」語意變成同一個命令的另一個參數） |
| M1.5 票 06 | 「隨機」排序跨頁會重洗 | 仍未處理（已知限制，與 jellyfin-web 相同） | `berth/domain/enums.py:658` `RANDOM` 仍在；替身 `adapters/jellyfin/fake.py:509` | 否 |
| M1.5 票 06 | `genres` 契約證據強度弱（DTO 不帶 `Genres`） | 仍未處理 | M1.5 票 11 維持原判 | 否 |
| M1.5 票 06 | adapter 四個過濾參數平鋪、`query` 一路傳 | 仍未處理（判斷題） | 同上 | 否 |
| M1.5 票 07 | `services/watch.py` 與 `watching.py` 名字相近 | 仍未處理（判斷題） | `berth/services/` 兩檔俱在 | 否 |
| M1.5 票 07 | Jellyfin 連不上沒有實跑 | 後續票已處理 | M1.5 票 11（`test_2_m15_library.py` 最後一條） | 否 |
| M1.5 票 08 | `jellyfin_link` 在 `services/inventory.py`（Feature Envy）；`watch.*` 與 `inventory.watch.*` 兩個 i18n 命名空間；`WatchTarget` 與 `MediaKind` 兩套字 | 仍未處理（判斷題） | `berth/services/inventory.py:703` | 否 |
| M1.5 票 08 | 一季上千集整季照畫、由 TMDB id 找作品每次整份拿回來比（代價沒量） | 後續票已處理（量測） | M2 票 11 | 否 |
| M1.5 票 08 | 研究 §9 第 5 點（10.11 回 0 退回遞迴查詢）不做 | 已不適用 | M1 票 14b 只支援 Jellyfin 12 | 否 |
| M1.5 票 09 | 「只看缺集」不寫進網址；收起段落 Ctrl+F 找不到 | 仍未處理（有意） | M1.5 票 11 維持原判；plan §11.3 B 組 | 否 |
| M1.5 票 10 | 缺集散在六季以上只退回作品名、不分批 | 後續票已處理 | M3 票 20（分批，`search_queries.py:138` 「季記號也放不下就分批」）；M4 票 107 拿掉站點請求預算，但分批與 `MAX_QUERIES` 留下 | 否 |
| M1.5 票 10 | 不能勾選幾集再搜；缺集模式不寫進網址 | 仍未處理（有意） | 沒有後續票；入口只有「整部 / 一季」 | 否 |
| M1.5 票 10 | 缺集搜尋不走 tmdbid | 已不適用 | 十個預設公開站都不支援 tmdbid，票內判斷；Torznab 於 M4 票 37 移除 | 否 |
| M1.5 票 11 | critique 小項：三頁 `h1` 大小與可見性、缺集搜 placeholder、`?page=2` 不畫兩列但沒說、電影牆 222 個 Tab 停留點 | 後續票已處理 | M2 票 03（h1）、M2 票 13 第 16 條（placeholder）、第 6/9 條（222 → 121 Tab 停留點，一頁 50 部） | 否 |
| M1.5 票 11 | `Poster.tsx` 與 `ArtSlot` 合併、`?filter=` 守衛共用、`tmdbText` 改名 | 後續票已處理 | M2 票 13；`web/src/i18n/displayRound.ts` 已取代 `tmdbText` | 否 |
| M1.5 票 11 | e2e 整部劇遞迴只驗到一季；`session` 失效斷言單獨撐不起；弱斷言 | 仍未處理 | 票內「記下、沒改」；`tests/e2e/test_2_m15_library.py` 未被後續票動 | 否 |
| M1.5 票 11 | 單項端點 `UserData` 讀不到整部劇遞迴標記結果（研究 §5 與實測不符） | 後續票已處理（票內修文件） | 研究 §5 與 brief §20.8 已補；e2e 斷言一律走清單端點 | 否 |

### 4.2 M2（子代理審計，我抽查 M5 相關列）

| 來源 | 發現 | 判定 | 依據 | 與 M5 相關？ |
| --- | --- | --- | --- | --- |
| M2 票 01 | `services/jobs.py` 的 `_by_id` 留著 `key` 參數（Speculative Generality，判斷為留） | 仍未處理（刻意保留） | `berth/services/jobs.py:1393`（定義）、`:1350-1354` 四個呼叫點 | 否 |
| M2 票 01 | `create_route` / `update_route` 外層仍各有一層 `_stale_write_as_missing`（判斷為不是重複） | 仍未處理（刻意保留） | `berth/services/routes.py:416, 442`（外層）、`:690`（定義） | 否 |
| M2 票 01 | `test_downloads.py::test_a_failed_round_drops_the_connection_so_the_next_one_starts_over` 名字超出它驗得到的範圍 | 仍未處理 | `tests/integration/test_downloads.py:954`（同名仍在）；連線身分另在 `test_qbit_poller.py:207` | 否 |
| M2 票 01 | `QbitPoller` 規則 1 的第一個測試是常數對常數（`tick_seconds == ACTIVE_INTERVAL`） | 仍未處理（Spec 軸認為夠） | `tests/integration/test_qbit_poller.py:144` | 否 |
| M2 票 01 | `test_free_space_reports_the_target_file_system` 對實時可用空間做等值比較而偶發紅 | 後續票已處理 | M2 票 16；`tests/unit/test_fs.py:427-431`（`FREE_SPACE_DRIFT = 256 MB` 容差） | 否 |
| M2 票 01 | 刪掉兩份 restricted fixture，brief §20.8「不帶 parentId 套權限」的實測證物不再留 repo | 仍未處理（記錄的取捨，無動作） | 票上改由 `useritems-resume.watching.json` / `shows-nextup.watching.json` 守；M3 票 06 Comments 補記「契約測試的 resume fixture 是不帶 parentId 錄的、respx 只比路徑」 | 否 |
| M2 票 02 | `web/src/api/schemas.ts` 的 `ROUTE_CHECKS` 仍是手寫字面聯集（`StepOut.step` 宣告成 `str`） | 仍未處理 | `web/src/api/schemas.ts:57-65`、`berth/api/schemas.py:37`（`step: str`）；M2 票 16 把它寫進 plan §11.3 D 組（`docs/plan.md:909`） | 否 |
| M2 票 02 | `AccessRefusal` / `RouteRefusal` 新增理由時「畫面要說一句話」沒有閘門（只有 `jobs.refusal.*` 有 `strictKeyChecks`） | 仍未處理 | 消費端仍是 `Partial<Record<RouteRefusal, string>>`：`web/src/settings/AddRoute.tsx:26`、`web/src/setup/buildRefusal.ts:13` | 是：命令登錄表要登錄「拒絕理由」，這三組 enum 就是它的來源，畫面對照沒閘門 |
| M2 票 02 | 三個 `*RefusalOut` model 的 `reason` + `detail` 同形（輕微重複，判斷為合理） | 仍未處理（刻意保留） | `berth/api/schemas.py`（OpenAPI 要各自名字才分得出三組） | 否 |
| M2 票 02a | `ROUTE_CHECKS` 手寫聯集沒做（要先另開 `RouteCheckOut`，否則舊 blob 讀取 500） | 仍未處理 | 同上；`web/src/api/schemas.ts:57`；`docs/plan.md:909`（D 組：不排里程碑） | 否 |
| M2 票 02a | `api/routes.py` 五支端點仍共用 `REFUSAL_RESPONSES`（九種理由聯集），`GET /jellyfin/libraries` 列得出它丟不出的 `route_in_use` | 仍未處理 | `berth/api/routes.py:80`（定義）、`:163, 180, 201, 220, 232`（使用） | 是：登錄表若從 `responses` 取每個命令的拒絕理由，這五支會多列理由 |
| M2 票 02a | `route_responses()` 定義在 `api/routes.py` 卻只有 `api/setup.py` 用（放錯家） | 仍未處理（刻意保留） | `berth/api/routes.py:69` | 否 |
| M2 票 02a | `route_responses()` 與 `api/jobs.py` 的 `_refusals()` 同形（Duplicated Code） | 仍未處理 | `berth/api/routes.py:69`、`berth/api/jobs.py:95` | 否 |
| M2 票 02a | `refusal?.reason === '…'` cascade 在前端散在多處（Repeated Switches），畫面那一句沒人守 | 仍未處理 | `grep -rn "refusal?.reason ===" web/src`（非測試檔 13 處） | 否 |
| M2 票 02a | 閘門的 `walk` 只跟同模組呼叫，跨模組委派會被讀成「不會拒絕」（假紅） | 仍未處理（刻意，docstring 已寫） | `tests/integration/test_openapi_contract.py`（`raised_models` docstring） | 否 |
| M2 票 03 | EN 頁標題與精靈散文叫 `Library paths`，子分頁已改 `Routes`，兩邊不一致 | 後續票已處理 | M2 票 16 先改成 `Routes`，M4 票 132 第 3 條推翻、改回 `Library paths` 並加閘門 `web/src/settings/settingsTitles.test.ts`；`web/src/i18n/resources.ts:4694, 6858` | 否 |
| M2 票 03 | 第 17 條：精靈每一步左欄剖面與右欄纜繩列仍是兩份實作（重構，可延） | 仍未處理 | `docs/plan.md:909`（D 組仍列）；M4 票 08 只做到「剖面不重複纜繩列的端點」（內容去重，非合併實作） | 否 |
| M2 票 03 | `.impeccable/design.json` 仍留語言鍵舊 Known contradiction，與 DESIGN.md 不一致 | 後續票已處理 | M2 票 13 第 18 項、M4 票 132 第 7 條（sidecar 重寫，規則 18→19） | 否 |
| M2 票 04 | `DeleteScope` 被編碼三次（service dataclass、端點四個 bool query 參數、前端型別） | 仍未處理 | `berth/api/jobs.py:481-504`（四個 bool 參數仍在）、`:32` | 是：刪除是 IRREVERSIBLE 命令，登錄表的 pydantic 輸入需要一份 scope model |
| M2 票 04 | DESIGN.md「就地確認」沒記 `ConfirmPanel` 第三種內容形狀 | 後續票已處理 | M2 票 16（`/impeccable document`，改寫成「一個外殼、四種內容形狀」） | 否 |
| M2 票 04 | 帳本寫法收不掉的路徑（含 `..`）時估算的檔案數多算一個（`reclaimable` / `freed` 正確） | 仍未處理（刻意，Berth 自己寫的路徑走不到） | `berth/services/deletion.py`（`_scope_paths` / `_measure` 去重） | 否 |
| M2 票 05 | 五種 Issue 型別（`source_missing` / `inode_mismatch` / `orphan_complete` / `unmanaged_library_file` / `job_without_files`）還沒有 producer | 後續票已處理 | M2 票 09（對帳其餘十種）；`berth/services/reconcile.py` 現有五型別 producer（`grep IssueType.<X>` 皆命中 reconcile.py） | 否 |
| M2 票 05 | 留給票 06：`IssueRow` 與 `ReviewRow` 共用列抽成 `QueueRow` | 後續票已處理 | M2 票 06；`web/src/components/QueueRow.tsx` | 否 |
| M2 票 05 | `unknown_torrent` 也寫進 `issues`（範圍蔓延），冪等鍵留給票 09 共用 | 後續票已處理 | M2 票 09 收成 `services/qbittorrent.unknown_torrents` / `unknown_torrent_detail`：`berth/services/downloads.py:68, 770`、`berth/services/reconcile.py:518-528` | 否 |
| M2 票 05 | 留給票 09：其餘十種檢查與它們的 `ISSUE_ACTIONS`（當時是空 tuple） | 後續票已處理 | M2 票 09 / 09c / 10；`berth/services/issues.py:956`（RELOOK 等已列入動作表） | 是：`resolve_issue` 的各動作是 M5 要逐顆標的命令（`services/issues` 仍在 `BEFORE_M3` 豁免表） |
| M2 票 06 | 同一筆 Job 有多個 audit 時，撤銷其中一個就把整筆拉回 `review`，其餘 audit 仍在媒體庫；核准會把撤銷過的列再入庫一次 | 後續票已處理（再入庫那一半；整筆拉回仍是現況） | M2 票 07 code-review：`_clear_item` 撤銷時把該列 action 設回 `REVIEW`、清提案（`berth/services/review.py:487-500`）；`_back_to_review` 仍整筆拉回（`review.py:459-479`） | 是：`undo_audit` 是 `confirm_audit(s)` 的 inverse，整筆 Job 回 review 的副作用要在 M5 登錄表裡說清楚 |
| M2 票 06 | `AuditRow` 與 `IssueRow` 動作列形狀相同，先不抽，等 `PlanRow` 出現再看 | 仍未處理（判斷題，未見後續票處理） | `web/src/review/`、`web/src/issues/IssueRow.tsx` | 否 |
| M2 票 06 | 沒有 `job_hash` 的帳本列（重新入庫建的）確認或撤銷時不寫任何事件 | 後續票已處理（票 10 決定沿用：無 Job 即無時間線） | `berth/services/review.py:415-419`（註解說「沒有鎖可拿，也沒有時間線可寫」，`if job is not None` 才 `record_event`） | 是：AI 對這類列的動作沒有 Event 可記（M5 要求每次呼叫記 Event），需另有落點 |
| M2 票 06 | 撤銷後 `AuditRow` 只重問 `['review']` 與 `['jobs']`，Media 詳情的 `awaiting_review` 不即時更新 | 後續票已處理 | M3 票 06：核准、撤銷、確認、修 Issue 之後 `['media']` 失效（M3 票 06 Comments「`['media']` 失效」） | 否 |
| M2 票 06 | 驗收「造 201 列」只用 issue 類造 | 已不適用 | M3 票 05 把 Issue 從 `/review` 拿掉（`docs/plan.md:404`，「`issue` 在 M3 票 05 拿掉」） | 否 |
| M2 票 07 | `PlanEditor` 的 `heavy` prop 名稱讀不出語意（沿用 `FileEntry`） | 仍未處理（刻意保留） | `web/src/review/PlanEditor.tsx` | 否 |
| M2 票 07 | `review_decided` payload 用 `PlanStatus` 值（`approved`/`rejected`），按鈕 enum 是 `PlanDecision`（`approve`/`reject`） | 仍未處理（刻意保留，兩端要一起改） | `berth/services/plan_review.py:169, 197`；`web/src/jobs/eventTypes.ts` | 是（弱）：AI 的核准/駁回要寫同一種 Event，詞彙不一致會進 AI 活動頁 |
| M2 票 07 | `target_exists` 的 Plan 不改那一列就核准會再撞一次、再停回 review，不擋 | 仍未處理（刻意，待有 repro） | `berth/services/plan_review.py`（核准路徑沒有磁碟讀取） | 否 |
| M2 票 07 | 使用者略過的字幕，影片改回入庫時不自動跟回來 | 仍未處理（刻意，`parser.revise` 註解） | `berth/parser/` 的 `revise` | 否 |
| M2 票 07 | Plan 的 `summary_json` 在 audit 撤銷後沒重算，佇列列的「要入庫 N 個 / 低 N」比表格舊一格 | 仍未處理 | `berth/services/review.py:474-478`（只換 `review_reason`）；對照 `plan_review.py:334` 逐列改才 `summarise()` 重算 | 是（弱）：AI 自動撤銷 audit 時摘要會是舊的 |
| M2 票 08 | `_duplicate_of` 的範圍衝突那一支照樣比自己的鏈接（刻意不對稱） | 仍未處理（刻意，docstring 已寫） | `berth/services/plan.py:681` | 否 |
| M2 票 08 | 對不到的字幕只能忽略，不能指派到某一集（沒排進任何票） | 仍未處理 | `docs/plan.md:909`（D 組：不排里程碑）；`berth/services/rematch.py` 只處理「字幕跟著影片走」 | 否 |
| M2 票 08 | 取代舊版時，被取代那筆 Job 的時間線上沒有事件 | 仍未處理（無 repro） | `berth/services/duplicates.py`（新的一筆有 `duplicate_decided`，舊的沒有） | 是（弱）：AI 活動頁要「逐筆撤銷」，被取代的 Job 沒有事件可對 |
| M2 票 08 | 同一集兩份重複同時下載完時規劃看不到彼此，後入庫者以 `target_exists` 停在 review | 仍未處理（無 repro） | `berth/services/plan.py` `_against_ledger` | 否 |
| M2 票 08 | `review` 情境展開區來源路徑在 Windows 開發機是反斜線 | 已不適用（容器為 POSIX，不處理） | `fs.under` 的 `Path` 呈現；票上已定 | 否 |
| M2 票 09 | 認領類三顆與管線三種動作範圍後移（票 10、票 09c），這票只按得了「忽略」 | 後續票已處理 | M2 票 10（認領）、M2 票 09c（管線）；`berth/services/issues.py:319-398`（`resolve_issue` 現有各動作分支） | 是：`resolve_issue` 是單一入口、各動作副作用等級不同，登錄表要拆開標 |
| M2 票 09 | 「畫面跟著變」只驗到 API 層，前端沒有另外的測試 | 仍未處理 | `tests/…/test_reconcile_checks.py::TestTheSeriesIdIsFilledIn` 為止 | 否 |
| M2 票 09 | `job_without_files` 的 forget 例外會漏報（很久以前 forget 過一件之後帳本全消失的那筆抓不到） | 仍未處理（無 repro） | `berth/services/reconcile.py:565` | 否 |
| M2 票 09 | `detail_json.action` 一鍵兩義（偵測時是 `PlanAction`，resolve 時被覆寫成 `IssueAction`） | 仍未處理 | `berth/services/issues.py:388`（覆寫）、`berth/services/reconcile.py:565`（依賴覆寫值）；`docs/plan.md:909`（D 組） | 是：M5 把「忽略 Issue」做成 Proposal 時要讀 `detail_json.action`，一鍵兩義會混淆 |
| M2 票 09 | 動帳本的按鈕（`_replace_with_link`）沒有拿 `job_lock`，stat 與 `replace_link` 之間有 `await`，audit 撤銷可能拆掉目標 | 仍未處理（無 repro） | `berth/services/issues.py:548-580`（此函式無 `job_lock`；`job_lock` 只在 `:625, 715`） | 是：AI 自動執行與人同時按會把單程序小窗口放大；services/issues 還在豁免表 |
| M2 票 09 | `RELOOK` 命名與 CONTEXT.md 的 Resolve 詞條拉扯 | 仍未處理（合規，UI 文案「重新反查」） | `berth/services/issues.py:363, 643`、`:956` | 否 |
| M2 票 09 | `_relook` 與 `_rescan` 尾部兩行重複 | 仍未處理（判斷題） | `berth/services/issues.py:643, 654` | 否 |
| M2 票 09c | Job 被別的路徑推走後，管線 Issue 停在 `open`，只剩「忽略」 | 後續票已處理 | M3 票 02（系統以 `resolved_by = system` 收）；`berth/services/issues.py:400`（`close_settled`）、`:976`；`docs/plan.md:947` | 否 |
| M2 票 09c | `IssueRow.tsx` 對 `issue.type` 的分支散四處；`jobs._reachable` 與 `issues._restart` 的 sign_in → 呼叫 → aclose 形狀重複 | 仍未處理（判斷題） | `berth/services/jobs.py:711-716`、`berth/services/issues.py:718-725`、`web/src/issues/IssueRow.tsx` | 否 |
| M2 票 09c | 5.x 上對停住的 torrent recheck → start 沒實測 | 後續票已處理 | M3 票 03（5.2.3 實測，順序改 start → recheck）；`docs/plan.md:178, 949` | 否 |
| M2 票 10 | 反解對「只有一個沒形狀的 token」兩可（`[X]` 發佈組還是版本名），Tags 會把版本名記成發佈組 | 仍未處理（無 repro） | `berth/services/ledger_rebuild.py`（反解） | 否 |
| M2 票 10 | `claim_file` 的 Job 由來源決定、作品由資料夾名決定，不互相核對 | 仍未處理（無 repro） | `berth/services/claims.py:336` 一帶 | 否 |
| M2 票 10 | `berth rebuild-ledger`（CLI）與服務是兩個程序，`job_lock` 管不到 | 仍未處理（無 repro） | `berth/services/ledger_rebuild.py`（無 `job_lock`） | 否 |
| M2 票 10 | importer 換落點時收掉舊鏈接是所有入庫路徑都會走到的（只收與來源同 inode 的） | 已不適用（刻意，已進 plan §3.1 / CHANGELOG） | `docs/plan.md:193` | 否 |
| M2 票 10 | `SYSTEM = "system"` 散在多個模組、`_user_id` 把 `actor_of` 字串解析回 int | 仍未處理（判斷題） | `berth/services/downloads.py:141`、`berth/services/ledger_rebuild.py:40` | 是：M5 要加 AI actor，actor 字串約定散在各模組 |
| M2 票 10 | 前端 `CLAIM_MISSES` 手抄後端 `ClaimMiss`（在沒型別的 `detail` dict 裡，OpenAPI 產不出） | 仍未處理 | `web/src/issues/IssueRow.tsx:364-367` | 否 |
| M2 票 10 | `IssueResolveIn.media` 用空字串代表沒選 | 仍未處理 | `berth/api/issues.py:175`（`media: str = ""`） | 是：登錄表的 pydantic 輸入應用 `None`/選填，不是哨兵字串 |
| M2 票 10 | `_media_of` 與 `ensure_media` 同一個形狀 | 仍未處理（判斷題） | `berth/services/claims.py:265, 445` | 否 |
| M2 票 10 | 演示伺服器從 `tests.integration.test_media` 借替身 TMDB | 仍未處理（刻意，import 行寫了理由） | `scripts/fake_setup_server.py` | 否 |
| M2 票 11 | 實驗腳本有重複、查詢參數手抄 adapter、直接呼叫 `services.inventory._survey` / `_routes` 私有函式 | 仍未處理（一次性腳本，刻意） | `scripts/experiments/large_library_berth.py:639-641` | 否 |
| M2 票 11 | `AccountDisabledError` 也涵蓋「刪除」，名實不符（對外 `account_disabled` 不能改） | 仍未處理 | `berth/services/jellyfin_access.py:132`；`docs/plan.md:909`（D 組） | 否 |
| M2 票 11 | `reuse` 那一輪兩個長尾（4c 200 部 848 ms、`limit=500` 8.8 s）要在穩定機器重量 | 仍未處理 | `docs/research/large-library.md`；M3 / M4 票皆無重量紀錄 | 否 |
| M2 票 12 | 底線連結 className 在 `JobDetailPage` 的 `INLINE_LINK` 與 `JobLink` 各一份，留給票 13 | 後續票已處理 | M2 票 13 抽成 `TEXT_LINK`：`web/src/components/controls.tsx:223`；`grep INLINE_LINK web/src` 已無 | 否 |
| M2 票 12 | 時間線「讀取中 / 讀不到 / 內容」三分支在詳情頁兩次、`JobRow` 一次 | 仍未處理（判斷題） | `web/src/jobs/` | 否 |
| M2 票 12 | 重新入庫在時間線上是 `retried`（`action: reimport`），計劃歷史只看得到後面那筆 `plan_generated` | 仍未處理（拍板接受的範圍） | `docs/plan.md:174` | 否 |
| M2 票 12 | 後端全套第一次跑 `test_reconcile_checks.py::TestInodeMismatch::test_twice_is_still_one` 因 guessit/rebulk 內部 `TypeError: 'ABCMeta'…` 紅過一次 | 仍未處理（無穩定 repro） | 全 repo 僅 M2 票 12 提到 `ABCMeta` | 否 |
| M2 票 13 | 第一次來（沒有上一次形狀紀錄）時繼續觀看那一行仍會位移，這是取捨本身 | 仍未處理（刻意取捨） | `web/src/watching/rememberedRows.ts:1-20`（無紀錄不佔位） | 否 |
| M2 票 13 | 庫存回應 `no-store` 無 `ETag`：不做自己的快取規則，建議之後做 JSON 壓縮 | 後續票已處理（壓縮那一半；ETag 刻意不做） | M3 票 06 加 `GZipMiddleware`（`berth/main.py:15, 119`，傳輸 759,826 → 215,747 bytes） | 否 |
| M2 票 13 | `PROXY_WIDTHS` 與後端 `IMAGE_SIZES`、`WALL_SIZES` 與 `WALL_GRID` 靠註解同步，沒有測試守 | 仍未處理 | `web/src/components/artSources.ts:5-6`、`web/src/components/wallGrid.ts:9-15`；`docs/plan.md:1035`（不排里程碑） | 否 |
| M2 票 13 | `useRememberedRows` 只在第一次畫時讀 key，`me` 不在快取時這次不佔位（目前走不到） | 仍未處理（走不到） | `web/src/watching/rememberedRows.ts` | 否 |
| M2 票 13 | `.impeccable/design.json` 沒有閘門（比對 DESIGN.md named rules 的測試），債第四次出現 | 仍未處理 | `grep -rln design.json web/src web/e2e tests` 無任何測試引用；M4 票 132 第 7 條只重寫了 sidecar；`docs/plan.md:909` | 否 |
| M2 票 13 | `RowPlaceholder` / `TilePlaceholder` 形狀相近、`TilePlaceholder inventory`、`Pager end` 兩個布林參數 | 仍未處理（判斷題） | `web/src/components/` | 否 |
| M2 票 13 | commit `b085c84` body 寫了量測值、兩個 commit scope 是 `web` 卻動後端對外介面 | 已不適用（歷史紀錄，已推不回） | 票 13 Comments | 否 |
| M2 票 14 | `services/review.py` 在 plan / unmatched 六個函式串 `library_id: str \| None`，第三種條件出現再改成條件物件 | 仍未處理（判斷題） | `berth/services/review.py:310-325, 597-628` | 否 |
| M2 票 14 | `.impeccable/design.json` 牆卡片描述仍寫 `MediaTile / InventoryTile`，留給票 16 | 後續票已處理 | M2 票 16（documenter，前提一半不對：併的是 `InventoryTile` 與集卡外框 `Tile`）、M4 票 132 第 7 條 | 否 |
| M2 票 14 | 媒體庫頁第一次來時「接著看」那一行晚出現、位移一行高（同票 13 取捨） | 仍未處理（刻意取捨） | `web/src/watching/rememberedRows.ts` | 否 |
| M2 票 14 | `abfe55a` 一個 commit 帶清單與搜尋兩件事 | 已不適用（歷史，不改歷史） | 票 14 Comments | 否 |
| M2 票 15 | 「0 列 UPDATE 拿 SQLite 寫鎖 + commit/rollback 骨架」在 `services/settings.py` 與 `services/routes.py` 各一份，第三處出現再抽 | 仍未處理（判斷題） | `berth/services/settings.py:13, 34`、`berth/services/routes.py:662-666` | 否 |
| M2 票 15 | `update_settings` 進門的 `commit()` 會連帶提交呼叫端尚未 commit 的寫入，之後失敗留「憑證存了、步驟沒記」半態 | 仍未處理（與 `routes._write_lock` 同取捨，docstring 有交代） | `berth/services/settings.py:34` | 是（弱）：設定類命令是 M5 的 irreversible/Proposal 範圍，半態風險要在登錄表命令邊界上考慮 |
| M2 票 15 | 精靈 e2e 不等加站跑完就測 TMDB，對時序敏感，CI 偶紅先看這裡 | 仍未處理（提醒項） | `web/e2e/wizard.spec.ts` | 否 |
| M2 票 16 | `/review` 的 CLS 0.08–0.097（`PlanRow` 佔位不夠高） | 仍未處理（M3 票 06 判定不做：低於 0.1，列數 1–39 固定佔位不成立） | M3 票 06 Comments 第 12 條 | 否 |
| M2 票 16 | `RematchEntry` 與 `PlanEditor` 打開時焦點沒送進表單 | 後續票已處理 | M3 票 06 第 1 條（`autoFocus`） | 否 |
| M2 票 16 | `JobDelete` 的 live region 是條件式掛載 | 後續票已處理 | M3 票 06 第 2 條（`role="status"` 一直掛著） | 否 |
| M2 票 16 | `QueueRow`「展開」命中區 60.7×11px | 後續票已處理 | M3 票 06 第 3 條（`min-h-6`，實測 24px） | 否 |
| M2 票 16 | Job 摘要列只有 audit 浮上來，對不到與重複待決沒有（要後端 `JobOut` 多兩個計數） | 仍未處理 | M3 票 06 第 13 條延後；`docs/plan.md:909`（D 組） | 否 |
| M2 票 16 | `/jobs` 的 h1 不是 `PAGE_TITLE` | 後續票已處理 | M3 票 06 第 4 條 | 否 |
| M2 票 16 | `/review` 段標題的計數沒有 sr-only 整句 | 後續票已處理 | M3 票 06 第 5 條（念成「2 件」） | 否 |
| M2 票 16 | 佇列列是絕對時間、Job 頁是相對時間；`whenText` 與 `Timestamp` 各自格式化 | 仍未處理 | `web/src/components/queueText.ts:13`、`web/src/components/Timestamp.tsx:11`；`docs/plan.md:909`（要先定全站慣例） | 否 |
| M2 票 16 | 送出中的鍵用 `disabled` 而不是 `aria-disabled` | 後續票已處理 | M3 票 06（`PrimaryButton`/`GhostButton` 的 `busy` 給 `aria-disabled`）；但「送出中用 `busy`」沒有掃描式閘門（`docs/plan.md:1035`） | 否 |
| M2 票 16 | `/issues` 進頁打兩次 `GET /issues` | 後續票已處理 | M3 票 06 第 7 條（`ReconcileBanner` 只記下不再失效） | 否 |
| M2 票 16 | JS bundle 746 KB 沒有壓縮與路由拆分 | 後續票已處理（壓縮做了、路由拆分量過後不做） | M3 票 06 第 8 條；`berth/main.py:119` | 否 |
| M2 票 16 | 同一張計劃卡上兩個同名「展開」 | 後續票已處理 | M3 票 06 第 9 條（`aria-labelledby`） | 否 |
| M2 票 16 | 「改」「修正」在桌機離檔名約 1100px | 後續票已處理 | M3 票 06 第 10 條（實測緊接檔名後 8px） | 否 |
| M2 票 16 | 七處輸入框 class 字串手寫，輸入框 `rule-strong` 規則沒有閘門 | 仍未處理 | `web/src/components/controls.tsx:67` 等；`docs/plan.md:909`（下一次改輸入框外觀時收常量） | 否 |
| M2 票 16 | `test_auth_api.py` 從 unit 測試模組 import `api_endpoints` | 後續票已處理 | M3 票 06 第 11 條；`tests/integration/test_auth_api.py:31`（`from tests.endpoints import api_endpoints`） | 否 |

### 4.3 M3（子代理審計，我抽查 M5 相關列）

| 來源 | 發現 | 判定 | 依據 | 與 M5 相關？ |
| --- | --- | --- | --- | --- |
| M3 票 01 | 第二個刪除請求在第一個 commit 之後才進來時，`removed → removed` 的 CAS 成立，伺服器分不出使用者看到的是不是刪除前的畫面；要堵得讓前端送 `expected_state` | 仍未處理 | `grep expected_state berth web/src` 0 筆；票 21 歸「沒有 repro」 | 否：刪除是 irreversible，M5 一律交人 |
| M3 票 01 | 重複版本「取代舊版」走 `fs.replace_link`，目標上若是使用者換進去的檔案會被蓋掉，沒有比 inode | 後續票已處理 | M3 票 21（「修掉」）；`berth/services/rematch.py:550-557` 先 `Placed.of(move.old).holds(facts)`，不成立丟 `TARGET_TAKEN` 才 `fs.replace_link` | 否 |
| M3 票 02 | 壞掉狀態之間不互通：`client_error` 的 Job 若客戶端改報 `missingFiles`，poller 不接回也不轉，Issue 給「重試」而非「重新校驗」 | 仍未處理 | `berth/services/downloads.py:410-412`（`_recover` 見 `status.state in BROKEN_STATES` 直接 `return False`）；票 21 歸「沒有 repro」 | 否 |
| M3 票 02 | `submit_failed` 接回時 Route 已被刪就不凍結資料夾名 | 仍未處理 | `berth/services/downloads.py:436-440`（`_freeze` 在 media 或 route 為 None 時什麼都不做） | 否 |
| M3 票 02 | 「system」actor 有多種寫法（`downloads.SYSTEM`、`actor_of(None)`），沒有收斂 | 仍未處理 | `berth/services/downloads.py:141` `SYSTEM = "system"`；`berth/services/jobs.py:1313-1316` `actor_of`；`berth/services/rss.py:156` `SYSTEM = actor_of(None)` | 是（弱）：M5 加 `ai` actor（`jobs.py:1315` docstring 已預告），命令登錄表要有一致的 actor 約定 |
| M3 票 03 | experiments 目錄裡 `docker()` 是近拷貝，下一支再要時收進 `lib.py` | 仍未處理 | `scripts/experiments/` 有 5 份 `def docker`（`compose_collisions.py:69`、`compose_profile_removal.py:65`、`jellyfin_permissions.py:184`、`jellyfin_username_rules.py:53`、`qbittorrent_stopped_recheck.py:93`），`lib.py` 沒有 | 否 |
| M3 票 04 | Issue 的「重新送單」`resubmit_job` 不看磁碟門檻（要補得先有「重新送單把磁碟塞滿」的 repro） | 仍未處理 | `berth/services/jobs.py:397`、`:495` 才有 `check_disk`；`resubmit_job`（`jobs.py:649`）沒有；票 21 歸「沒有 repro」 | 是：`resubmit_job` 是 Issue 動作，M5 若讓 AI 自動重新送單就繞過磁碟門檻 |
| M3 票 04 | 索引站報得出 hash 時 `job_removed` 在磁碟檢查前；報不出時先量磁碟，磁碟不夠期間 `removed` 的條目可能被拒成 `low_disk_space` | 仍未處理 | `berth/services/jobs.py:380-398`（docstring 明寫此代價），`check_disk` 在 `_resolve` 之前 | 否 |
| M3 票 04 | `check_disk` 與 `health_issues._disk` 量法相似（後者量兩個根、依 device 去重），未抽共用 | 仍未處理 | `berth/services/jobs.py:973`；`berth/services/health_issues.py:130` | 否 |
| M3 票 04 | `services/routes._gigabytes` 用 10⁹，而送單門檻用 1024³（GiB），既有不一致 | 仍未處理 | `berth/services/routes.py:1446-1448`（`/ 1_000_000_000`）對 `berth/services/jobs.py:1008-1010`（`/ 1024**3`） | 否 |
| M3 票 05 | `confirm_audit(s)` 的反向命令標成 `review.undo_audit`，語意對不上（`undo_audit` 拆掉入庫，且拒絕已確認的列 `not_audited`）；M5 要決定另立「取消確認」或改 `inverse=None` | 仍未處理 | `berth/services/review.py:347`、`:365` 仍是 `inverse="review.undo_audit"`；plan §11.6 已列為登錄表開工時要處理的兩條之一 | 是：命令登錄表的反向命令語意（plan §11.6），AI 任務「audit 的確認或撤銷」直接用它 |
| M3 票 05 | 主要原因認不出「以標題認出作品但不精確」那一支（`MEDIA_BY_TITLE` 精確與不精確都會出現），RSS 那路收起的列仍說「信心 medium，已自動入庫」 | 仍未處理 | `web/src/review/leadReason.ts:16-28` 的 `LEADS` 沒有 `media_by_title`；`berth/parser/mapping.py:794` | 否 |
| M3 票 05 | `LEADS` 與解析器「哪些理由會壓到 medium」之間沒有閘門連著 | 仍未處理 | §11.5 遺留（「不排里程碑」）；`tests/unit/test_reason_codes.py` 只比兩語佔位符與 `lead` 句子表，不比解析器的理由集合 | 否 |
| M3 票 05 | `auditGroups.ts` 兩個迴圈各算一次分組鍵；帶 `library` 時 `GET /review` 也問一次 `count_open` | 仍未處理 | `web/src/review/auditGroups.ts:34`、`:40` 各呼叫 `groupKey`；`berth/api/review.py:314` 仍取 `count_open` | 否 |
| M3 票 05 | `services/issues` 在豁免表卻有 `count_open` 已標記（半標） | 仍未處理 | `berth/services/issues.py:240-258`（三個 `Effect.READ`），`resolve_issue`（`:319`）未標；`tests/unit/test_command_marks.py` 的 `BEFORE_M3` 仍列 `issues`（共 41 個模組） | 是：登錄表開工要逐顆標 `services/issues`（plan §11.6） |
| M3 票 05 | API handler 叫 `post_confirm_many`、service 叫 `confirm_audits`，命名不一致 | 仍未處理 | `berth/api/review.py:335`；`berth/services/review.py:366` | 否 |
| M3 票 06 | 核准之後入庫是背景的，開著詳情頁的人要等 5 分鐘 staleTime 或重新整理（詳情頁沒訂 SSE） | 後續票已處理 | M4 票 12、132：`useJobStream` 移到 `DownloadsPanel` 頂端、`useSeasonsFollow` 讓季表重問（`web/src/media/DownloadsPanel.tsx:51-52`）；票 132 表第 4 列 | 否 |
| M3 票 06 | `['media']` 失效散在六處（這票加四處），要收成 `api/media.ts` 一支 helper | 仍未處理 | `grep "invalidateQueries.*media"` 現有 13 處（`web/src/**`，不含測試），未見共用 helper | 否 |
| M3 票 06 | `router.ts` 兩段 `subscribe` 形狀幾乎一樣；`controls.tsx` 兩顆按鈕各寫一次 `aria-disabled:` 外觀 | 仍未處理 | `web/src/router.ts:41`、`:46`；`web/src/components/controls.tsx:177`、`:197` | 否 |
| M3 票 06 | `watching_out` 只剩 `api/inventory.py` 在用，仍住在 `api/jellyfin.py` | 仍未處理 | `berth/api/jellyfin.py:180`；`berth/api/inventory.py:24`、`:278` | 否 |
| M3 票 06 | `onUnapplied` 從 `PlanEditor` 往下傳三層，再多一層該改 context | 仍未處理 | `grep onUnapplied web/src`（非測試）12 處，尚未改 context（未逐層重驗層數） | 否 |
| M3 票 06 | 「送出中用 `busy`」沒有靜態閘門，要收成規則時補一條掃 `disabled={…Pending}` 的測試 | 仍未處理 | §11.5 遺留；`web/src/lint.test.ts` 無此掃描；現仍有 `web/src/rss/OneshotList.tsx:134` `disabled={send.isPending}`、`web/src/pages/LoginPage.tsx:84,94` | 否 |
| M3 票 06 | 契約測試 `useritems-resume.watching.json` 是不帶 `parentId` 錄的，現在呼叫都帶 `parentId`，respx 只比路徑，「帶了真的會過濾」沒被驗到 | 仍未處理 | `tests/integration/test_adapter_contracts.py:3163` 註解仍說錄製時不帶 `parentId` | 否 |
| M3 票 06 | M2 票 16 遺留 8：路由拆分量了不做（入口 chunk 759→457 kB 可省約 70 kB gzip，嫌要動 `AppShell`） | 仍未處理 | `grep lazyRouteComponent\|React.lazy web/src` 0 筆；票 21 audit 量到 898 KB 單一 chunk（P2 不修） | 否 |
| M3 票 06 | M2 票 16 遺留 12：`/review` 的 CLS 0.08–0.097（低於 0.1）不做 | 仍未處理 | 刻意不做的決定；票 21 audit 另量到輪詢後待綁定推開畫面的 CLS 0.74，已以 `bringBack` 修（那是另一條） | 否 |
| M3 票 06 | M2 票 16 遺留 13：Job 摘要列只浮上 audit，對不到與重複待決沒有（要後端 `JobOut` 多兩個計數） | 仍未處理 | plan §11.3 D 組（`docs/plan.md:909`）；`berth/api/schemas.py` 的 `JobOut` 無對應計數欄 | 否 |
| M3 票 06 | M2 票 16 遺留 14/15：佇列列是絕對時間、Job 頁是相對時間，`whenText` 與 `Timestamp` 各自格式化 | 仍未處理 | plan §11.3 D 組；`web/src/components/queueText.ts`（`whenText`，被 `web/src/rss/ItemLine.tsx:40`、`rss/grounds.ts:37` 用）與 `web/src/components/Timestamp.tsx` 兩份並存 | 否 |
| M3 票 06 | M2 票 16 遺留 16/17：七處欄位 class 字串手寫；輸入框 `rule-strong` 規則沒有閘門 | 仍未處理 | plan §11.3 D 組；`grep rule-strong web/src` 90 處（含非輸入框），無「都用同一常量」的測試 | 否 |
| M3 票 06b | 精靈第 2 步剖面與纜繩寫死 `qbittorrent:8080/api/v2/app/version`（`signals.ts` 的 `PROBE_ENDPOINT`），換 port 後畫面寫錯 | 後續票已處理 | M3 票 06h（`probe_targets`），其後 M4 票 15 把探測改成使用者選擇，現在 `grep PROBE_ENDPOINT\|probe_targets berth web/src` 0 筆 | 否 |
| M3 票 06b | 精靈跑完後再改 `QBITTORRENT_WEBUI_PORT`，Berth 不會跟著走（`QbittorrentSettings.base_url` 在第 4 步存下） | 仍未處理 | §11.4 延後（`docs/plan.md:965`）；`berth/services/qbittorrent.py:468-476` `qbittorrent_target` 仍回存下的 `settings.base_url`；`docs/guide/troubleshooting.md:35` 寫「跑精靈前先定」 | 否 |
| M3 票 06b | 同一套上重跑偵測會把已跑完初始精靈的套件內 Jellyfin 判成 `existing`（Route 那步因此沒自動建） | 已不適用 | 票 21（「修掉」，commit `d03f6dd7`）；M4 票 15 之後偵測判定整個改成使用者選擇（`berth/migrations/versions/f3c9a1d6b2e8_m4_setup_choices.py` 拿掉 `settings.setup.services`） | 否 |
| M3 票 06b | 試跑環境 `C:\Users\Roxy\berth-trial\` 的 `HostHeaderValidation=false` 與舊 compose 要由使用者重置 | 後續票已處理 | M3 票 06h「第 6 條的準備」：備份後改用 repo 的 compose 與 `deploy/preseed/`；repo 內 `deploy/preseed/` 與 `config/qbittorrent` 搜不到 `HostHeaderValidation` | 否 |
| M3 票 06b | 五個 API 端點重複寫 `JellyfinWebOut.model_validate(await jellyfin_web(...))`，可收成一個相依 | 仍未處理 | `grep "JellyfinWebOut.model_validate" berth/api/*.py` 5 處（`inventory.py:228`、`jellyfin.py:186`、`media.py:316` 等） | 否 |
| M3 票 06b | `env_file` 可改用 `python-dotenv`（目前只是傳遞依賴） | 仍未處理 | `pyproject.toml` 無 `python-dotenv`，只在 `uv.lock:965`；`tests/unit/test_deploy_ports.py`、`tests/e2e/stack.py` 仍自己處理 | 否 |
| M3 票 06b | `qbittorrent_target` 在沒偵測過時回空字串（docstring 說明） | 已不適用 | M4 票 15：`berth/services/qbittorrent.py:471-476` 現在「還沒選是 `None`，寫入的命令一律拒絕」 | 否 |
| M3 票 06c | 帳號屬於 Jellyfin 之後只想取消勾選仍要打一次密碼（`AdminIn.password` `min_length=1`） | 已不適用 | M4 票 06（commit `ef382368`）刪掉 `AdminStep.tsx` 與管理員步驟（`grep class AdminIn berth` 0 筆） | 否 |
| M3 票 06c | Data Clumps：介面帳號與密碼在 `qbittorrent.py`、`indexer.py` 各拆一次，等第三個消費點再包 | 後續票已處理 | M4 票 07：`berth/services/steps.py` 的 `InterfaceLogin`、`berth/api/schemas.py:78-98` `InterfaceLoginIn.value` | 否 |
| M3 票 06c | `CutawayLine['key']` 的九個 i18n key 是手寫 union，改文案鍵要兩處同步 | 已不適用 | `grep CutawayLine web/src` 0 筆；M4 票 06/15 重做精靈步驟（改成 `ChoiceCutaway.tsx`） | 否 |
| M3 票 06c | `AdminStep.tsx` 的 `words` 兩份結構相同；`applyHint` 前半句重複 | 已不適用 | `web/src/setup/AdminStep.tsx` 不存在（M4 票 06，commit `ef382368`） | 否 |
| M3 票 06d | `SetupPage.tsx` 十個 mutation 各寫一次 `onMutate: hold`（Duplicated Code） | 後續票已處理 | M4 票 30：網址 `?step=N` 為唯一來源，「原本的 `pinned` 與 `hold` 刪掉」（commit `958313fb`）；`grep "onMutate: hold" web/src` 0 筆 | 否 |
| M3 票 06d | `note`/`nav`/`redetect` 三個 slot 一起進五個步驟元件（Data Clumps）；「步驟→頁/泊位」散在多張表 | 仍未處理 | 06e 收掉 `pageOf`/`REVISIT_PAGE` 後仍剩 `web/src/setup/navigation.ts:33` `BERTH_STEP` 與 `web/src/setup/BerthNav.tsx:98` `REVISIT` 兩張；`redetect` slot 已隨偵測移除 | 否 |
| M3 票 06d | 只重探一個服務時，前端整輪輪詢會連帶重探其他尚未手動接好的服務 | 已不適用 | M4 票 15 拿掉自動偵測與輪詢視窗（`probe_started_at` 在 `f3c9a1d6b2e8_m4_setup_choices.py:83` 移除） | 否 |
| M3 票 06d | 手動接好（`configured`）的服務不給「重新偵測這個服務」 | 已不適用 | M4 票 15：偵測改成使用者在服務頁二選一並自行「重新測試」，無 `configured` 旗標 | 否 |
| M3 票 06e | 泊位 slot 鍵仍叫 `'prowlarr'`（那格也可能是 Torznab）；`BerthBoard`/`HealthBoard` 各自 `if slot === 'tmdb'/'library'` 分支 | 仍未處理 | `web/src/components/berths.ts:30` `slot: 'prowlarr'`；`web/src/health/HealthBoard.tsx:24`、`:33` 的 slot 分支；Torznab 疑慮已被 M4 票 37（BTH 4 只支援 Prowlarr）消掉，剩分支重複 | 否 |
| M3 票 06e | `remove_indexer` 與 `apply_default_indexers` 各寫一份「非套件內就拒絕」守門；`(indexer_id, definition_name, name)` 一起穿過 `_search_site` 與 `SiteSearch`（Data Clumps） | 仍未處理 | `berth/services/indexer.py`（`remove_indexer`、`apply_default_indexers`）仍各自守門；未逐行重驗 Data Clumps | 否 |
| M3 票 06e | 「站」與「索引站」兩詞混用（`SiteSearch`、`TrialSite` 對 `IndexerOption`） | 仍未處理 | 判斷題，票 21 歸「不做」；`web/src/setup/IndexerSites.tsx` 仍用 `TrialSearchResult` / site 字樣 | 否 |
| M3 票 06e | 06d 留下的 `onMutate: hold` 與四張步驟表未收 | 後續票已處理 | 前者見 M4 票 30（`hold` 已刪）；後者 06e 已併成兩張，剩餘見 06d 列 | 否 |
| M3 票 06f | `BundledLibraryIn`（api）、`LibraryDraft`（Protocol）、`BundledLibrary`（model）、`BundledLibraryView` 四個形狀相近 | 仍未處理 | `berth/api/setup.py:587`、`berth/services/jellyfin.py:158`、`:174`、`berth/models/setting.py` | 否 |
| M3 票 06f | 前後端兩份媒體庫規則沒有共用 fixture 當閘門，哪邊改規則另一邊不會紅 | 仍未處理 | `web/src/setup/libraryRules.ts` 與 `berth/services/jellyfin.py` `check_bundled_libraries` 各自的測試；僅有 `web/src/setup/librarySlug.examples.json` 一份範例（疑為共用，未逐條比對） | 否 |
| M3 票 06f | 重跑時有新建也有已存在的，纜繩只列新建的名字 | 仍未處理 | 未見後續票處理；票 21 歸「不做」（行為沿用） | 否 |
| M3 票 06f | 在 Jellyfin 刪掉的媒體庫，清單那一列會解鎖、重跑照清單建回來 | 仍未處理 | 刻意行為（「由清單決定」）；票 21 歸「刻意的行為」 | 否 |
| M3 票 06f | `DEFAULT_METADATA_FETCHERS` 兩種類型的值一樣（票面要依內容類型給預設值） | 仍未處理 | `berth/services/jellyfin.py:124` | 否 |
| M3 票 06f | 欄位名 `folder` 與 CONTEXT.md 的 **Folder Name**（作品資料夾）同字 | 仍未處理 | 判斷題；`berth/models/setting.py:62` 附近仍用 `folder` | 否 |
| M3 票 06g | 後端視窗沒重算時，指名重探一台剛起來的服務會立刻判既有/逾時，不再等一個視窗 | 已不適用 | M4 票 15：`probe_started_at` 與 `_settled` 視窗整個移除（`f3c9a1d6b2e8_m4_setup_choices.py:83`） | 否 |
| M3 票 06g | 視窗內「探測中 · 連得上，但回的東西不是這個服務」理由與等待提示不一致 | 已不適用 | 同上，探測視窗與 `protocol_mismatch` 判既有的機制已隨 M4 票 15 移除 | 否 |
| M3 票 06g | `windowMs` 在 status 未載入時是 0，第一次失敗就算放棄 | 已不適用 | `grep windowMs\|failingSince web/src` 0 筆（M4 票 15） | 否 |
| M3 票 06g | `failingSince` 在兩處歸零（探到了、使用者按新一輪），兩個理由沒合併 | 已不適用 | 同上 | 否 |
| M3 票 06h | 既有 Jellyfin 帳密錯只顯示「失敗 POST /Users/AuthenticateByName: 401」，該改成「帳號或密碼不對」 | 後續票已處理 | M4 票 21（commit `1bd4170b` 錯誤分層）；`web/src/i18n/resources.ts:357`、`:1179`「帳號或密碼不對」；§11.4 延後曾列此條 | 否 |
| M3 票 06h | 選填索引站連不上塗阻擋紅、每站一個 `role=alert`（4 條同時念） | 已不適用 | M4 票 09/81 重做索引站步驟；`web/src/setup/IndexerSites.tsx`、`IndexerStep.tsx` `grep role="alert"` 0 筆 | 否 |
| M3 票 06h | 同名控制項（索引站「移除」×5、「複製」×4；既有服務第 2 步「位址」「測試連線」×3、「顯示」×2 無 `aria-pressed`） | 仍未處理 | `removeNamed` 只在 `web/src/setup/BundledLibraries.tsx:200`；`grep aria-pressed web/src/setup` 0 筆（未逐一重驗索引站「移除」與「複製」） | 否 |
| M3 票 06h | 標題跳號：纜繩列手動步驟用 h5 跳過 h4 | 仍未處理 | `web/src/setup/QbittorrentStep.tsx:234`、`ServiceChoice.tsx:1076`、`web/src/components/StepLine.tsx:84` 仍是 `<h5>` | 否 |
| M3 票 06h | 淺色主題錯誤狀態輸入框邊框 `blocked` 對 `hull` 2.58:1（WCAG 1.4.11） | 後續票已處理 | M3 票 21（commit `d03f6dd7`）；`web/src/components/controls.tsx:67` 用 `border-blocked-ink`，`web/src/index.css:30`、`:63` 淺色另設較深的 `blocked-ink` | 否 |
| M3 票 06h | 精靈沒有路由切分（入口 800 KB） | 仍未處理 | 同 06 路由拆分一列：`grep lazyRouteComponent web/src` 0 筆 | 否 |
| M3 票 06h | 觸控目標：ZH/EN 44×24、「顯示」39×24、Ghost 按鈕 35px 高，過 2.5.8 的 24px 但未達 44 | 仍未處理 | `web/src/components/controls.tsx:215-216` `COMPACT_BUTTON` `min-h-6`；票 21 audit 也以 P2 不修 | 否 |
| M3 票 06h | 移除媒體庫列之後焦點掉回 body（`BundledLibraries` 沒用 `useFocusAfterRemoval`） | 後續票已處理 | M3 票 21（「修掉」）；`web/src/setup/BundledLibraries.tsx:6`、`:38` 已用 `useFocusAfterRemoval` | 否 |
| M3 票 06h | `SetupPage.tsx` 輪詢 effect 依賴每次 render 都是新物件的 `detect`，重繪重設 3 秒計時器 | 後續票已處理 | M4 票 15/30 重寫輪詢（`web/src/pages/SetupPage.tsx:477`、`:517` 改用 `refetchInterval`）；M4 票 92 另把 `useWaitingRetest` 相依整理過 | 否 |
| M3 票 06h | 泊位 1 套件內剖面「將會做什麼」與右欄序列同 7 列（plan §11.3 D 組已記）；泊位板一格寫來源不寫狀態 | 仍未處理 | plan §11.3 B/D 組延後（`docs/plan.md:909`「精靈左欄剖面與右欄纜繩列兩份實作」）；票 21 歸「不做」 | 否 |
| M3 票 06h | 「套用這 5 個鍵」下列 6 列；qBittorrent 套用後「建議值」欄變「已經是這樣」看不到原值 | 已不適用 | 精靈 qBittorrent 步驟於 M4 票 07/15/101 重做；`web/src/i18n/resources.ts:196` 只剩 `skipped: '已經是這樣'` 一處，未重驗原值是否顯示 | 否 |
| M3 票 06h | Route 建好之後剖面「這一輪要建的 Route 0」 | 已不適用 | 路由步驟於 M4 票 08/43 重做（頁 3 自動跑）；逐項未重驗 | 否 |
| M3 票 06h | Prowlarr key 的位置兩處寫法不同（設定 → 一般 → 安全性 / 設定 → 一般） | 仍未處理 | 未見後續票處理；票 21 歸「不做」（未重驗文案） | 否 |
| M3 票 06h | 第 2 步的「上一個泊位」回到的是管理員 | 已不適用 | M4 票 06（`ef382368`）刪掉管理員步驟，導覽改 `?step=N`（票 30） | 否 |
| M3 票 06h | 既有 Jellyfin 做完「重新登入」仍是黃色主要鍵 | 仍未處理 | 票 21 歸「不做」；`web/src/setup/JellyfinExisting.tsx` 未重驗 | 否 |
| M3 票 06h | qBittorrent 分類 `berth-電影` 中文進了機器 token | 仍未處理 | 未見後續票；分類由媒體庫名組出，`berth/services/routes.py` 仍用 slug（未逐項重驗是否仍帶中文） | 否 |
| M3 票 06h | 冷啟動第一秒寫「連得上，但回的東西不是這個服務」會嚇人 | 已不適用 | M4 票 15 移除探測視窗與 `protocol_mismatch` 等待文案 | 否 |
| M3 票 06h | 管理員欄位留空時錯誤念兩次 | 已不適用 | 管理員步驟已刪（M4 票 06） | 否 |
| M3 票 06h | 設定頁 Jellyfin 健康卡的「3 libraries」是英文（後端 detail 字串） | 後續票已處理 | M3 票 21（commit `d03f6dd7`，`berth/services/health.py` +8 行）；票 21「修掉」清單 | 否 |
| M3 票 06h | 術語「開始靠泊」「冪等」「complete 根目錄」「dev=/inode=」對第一次架設的人是黑話 | 後續票已處理 | M4 票 103（wizard copy leftovers）；`grep 開始靠泊\|冪等 web/src/i18n/resources.ts` 0 筆（`dev=`/`inode=` 仍在纜繩原文，未逐項重驗） | 否 |
| M3 票 06h | 冷啟動 e2e 閘門守的是 06g 的探測視窗（`protocol_mismatch`→`starting`），視窗機制已刪後閘門只剩「冷啟動第一輪不得全部判定完成」的斷言形狀 | 已不適用 | M4 票 15 刪探測視窗；`tests/e2e/conftest.py` `configured` 隨精靈改版（未逐行重驗斷言是否仍有意義） | 否 |
| M3 票 06i | `routes.tsx` 仍逐條寫五個設定路徑，`components/berths.ts` 的 `settings` 欄是第二份 | 仍未處理 | `web/src/routes.tsx:529-534` 與 `web/src/components/berths.ts:20-32` | 否 |
| M3 票 06i | `IndexerActions`/`TmdbKey` 自帶 `mt-6`，設定頁用 `[&>:first-child]:mt-0` 壓掉 | 仍未處理 | `web/src/pages/IndexerSettingsPage.tsx:116`、`web/src/pages/TmdbSettingsPage.tsx:35` | 否 |
| M3 票 06i | 「讀取中/讀不到/資料」三態在 `HealthSection`、`ServiceConnection`、索引站頁、TMDB 頁各寫一份，說法不同 | 仍未處理 | 判斷題，票 21 歸「不做」；未逐檔重驗 | 否 |
| M3 票 06i | `settings.jellyfin.*` 與 `settings.jellyfinPage.*` 兩組鍵名不易分辨 | 仍未處理 | `web/src/i18n/resources.ts` 仍兩組並存（未逐鍵重驗） | 否 |
| M3 票 06i | 「加入這 N 個站」的 N 含已經在的站（會重驗一次標「已經是這樣」） | 已不適用 | 索引站步驟 M4 票 09/81 重做；`grep "加入這" web/src/i18n/resources.ts` 0 筆 | 否 |
| M3 票 07 | 同一個發佈在 Mikan 與 acg.rip 是不是同一個 info hash（要下載 acg.rip `.torrent`） | 仍未處理 | `docs/research/rss-sources.md:570-577`〈11. 沒解的〉仍列；票 21 歸「記錄項」 | 否 |
| M3 票 07 | MyBangumi 的上限是筆數還是時間窗；Mikan GB 級大小單位；acg.rip 搜尋 feed 30 筆上限與分頁 | 仍未處理 | `docs/research/rss-sources.md:572,574-575` 同上，三條都仍在「沒解的」 | 否 |
| M3 票 07 | `feedparser` 不進專案依賴，票 08 加依賴時再決定腳本要不要改用專案環境 | 後續票已處理 | M3 票 08：`pyproject.toml:13` `feedparser>=6.0.14`；`scripts/experiments/rss_sources.py:13` 已改成 `uv run python scripts/...` | 否 |
| M3 票 07 | 三站欄位表在 brief §20.12、plan §8.5、研究檔 §9 三處重疊，改一處要同步 | 仍未處理 | 判斷題；三處仍並存（`docs/design-brief.md` §20.12、`docs/plan.md` §8.5、`docs/research/rss-sources.md`） | 否 |
| M3 票 08 | `SeriesBinder` 的搜尋與結果清單與 `issues/WorkPicker.tsx` 幾乎同形，第三個出現時抽共用 | 後續票已處理 | M3 票 18 抽出 `Choices` 與 `preselect`（`web/src/rss/WorkChoices.tsx`、`rss/preselect.ts`）；票 21「已修」；但票 18、19 的 Comments 記下剩餘重複（`OneshotSection.WorkPicker`、`SubscribePanel.Options<T>`），見票 18/19 列 | 否 |
| M3 票 08 | `services/rss._parse` 與 `_series_key` 各自 `match kind`，鍵是字串再 `split`；加第二種來源時改成依 `FeedKind` 查的一個 mapper | 仍未處理 | `berth/services/rss.py:1009`、`:1122`、`:2579` 三處 `match kind`（票 11 後來又列「來源分支散在五處」） | 否 |
| M3 票 08 | 命名 `RssItem`/`ItemView` 與 adapter 的 `FeedItem`、enum 的 `FeedItemStatus` 不一致（CONTEXT 詞是 Feed Item） | 仍未處理 | `berth/models/rss.py:135`、`berth/services/rss.py:330`、`berth/adapters/rss/__init__.py:19`、`berth/domain/enums.py:1564` | 否 |
| M3 票 08 | `SeriesOut.submitted` 只有綁定回的那一份有值，先留著並在欄位註解說明 | 仍未處理 | `berth/api/rss.py:224/239/256/344` 多個回應仍帶 `submitted: int`；未見拆型別 | 否 |
| M3 票 08 | `delete_feed` 標 `reversible`：Item 的 `error` 與 Feed 的 `interval_sec` 回不來，但送出的與綁定回得來 | 仍未處理 | `berth/services/rss.py:670-671` 仍 `@command(Effect.REVERSIBLE, inverse="rss.add_feed")`；plan §11.6 要重看（`delete_feed` 連帶 CASCADE 刪 Feed Item，反向 `add_feed` 還原不了） | 是：plan §11.6 點名「`rss.delete_feed` 標可逆」，AI 只做可逆命令，標錯等於放行 |
| M3 票 08 | 綁完待綁定段最後一列時焦點落在 Feed 段第一列而非段落標題；`Loading` 用 `well` 框而非 `deck` | 仍未處理 | 判斷題；M4 票 13 重做 RSS 頁（`web/src/rss/SeriesSection.tsx`、`seriesByWork.ts`），未逐項重驗 | 否 |
| M3 票 08 | `pipeline/rss.py` 又一份 `Sleeper`/`Clock` 型別別名（第五個迴圈） | 後續票已處理 | M4 票修補段 commit `515a2cf2`（建立 `berth/pipeline/ticks.py:25-26` 共用別名）；`berth/pipeline/rss.py:36-37` 現用共用的 `Sleeper`/`Clock`（`services/indexer.py:92` 仍有一份） | 否 |
| M3 票 08 | （附註）`rss.poll_due` 在 08 出生時標 `REVERSIBLE`；plan §11.6 指出背景迴圈入口標可逆，登錄表會把它當 AI 工具 | 仍未處理 | `berth/services/rss.py:844-845` `@command(Effect.REVERSIBLE)`，唯一呼叫端是 `berth/pipeline/rss.py:18` | 是：plan §11.6 點名「`rss.poll_due` 標成 `REVERSIBLE`」 |
| M3 票 09 | 後端叫 reasons（`BindReason`、`reasons_json`），時間線與 i18n 叫 grounds | 仍未處理 | `berth/models/rss.py:124` `reasons_json`；`web/src/rss/grounds.ts`、`GroundsList.tsx` | 否 |
| M3 票 09 | 實驗腳本 import `services.rss` 的私有 `_clues`、`_candidates` | 仍未處理 | `scripts/experiments/rss_auto_bind.py:34` | 否 |
| M3 票 09 | `SYSTEM = actor_of(None)` 是 services 裡第四份 `system` | 仍未處理 | `berth/services/rss.py:156`（另見 02 列的 `downloads.py:141`） | 是（弱）：同 02，actor 約定 |
| M3 票 09 | `_auto_bind` 回 `int \| None`（送出幾筆／沒綁） | 仍未處理 | `berth/services/rss.py:1762-1770` | 否 |
| M3 票 09 | 對到第 2 季以後時沒把季號寫回 `RssSeries.season`（票 13 的範圍） | 後續票已處理 | M3 票 13（票 21「已修」：季號寫回 RSS Series）；`berth/services/series_review.py:170` `series.season, series.episode_offset = season, offset` | 是：AI 任務「RSS Series 季號與 offset 修正」用的就是這條寫回路徑 |
| M3 票 09 | 查不到（`lookup_failed`）不重試 | 後續票已處理 | M4 票 14：`berth/services/rss.py:138`、`:1744-1759` 暫時失敗退避重認（`lookup_retry`），用完才落 `lookup_failed`；brief §15 | 否 |
| M3 票 09 | bgm.tv 連結沒用上（TMDB 不收 bgm 的 id） | 仍未處理 | `docs/design-brief.md:572` 仍寫「bgm.tv 連結沒有用上」；`grep bgm berth/services/rss.py` 0 筆 | 否 |
| M3 票 09 | Route 那一步在真實環境一部都綁不上（TV 與 Anime 都收劇集 → 全部 `route_ambiguous`），規則要不要改等使用者拍板 | 後續票已處理 | M3 票 21（使用者拍板 Feed 帶一條 Route，`_chosen_route`）、M4 票 105（Route 必填）；`berth/services/rss.py:1818`、`:1973` | 否 |
| M3 票 10 | `_rescreen` 先讀再寫：輪詢剛好把其中一筆送出去，會被改回 `excluded`（Job 照跑）；要改條件式 `UPDATE … WHERE status IN (…)` | 仍未處理 | `berth/services/rss.py:1623-1640` 仍是讀出 Item 再逐筆改 `item.status`；§11.4 延後（`docs/plan.md:965`） | 否 |
| M3 票 10 | `_in_library` 與 `services/plan._duplicate_of` 比對形狀相近，刻意不合併 | 仍未處理 | 判斷題；`berth/services/plan.py:727` 與 `rss.py` 的 `_in_library` 仍分開 | 否 |
| M3 票 10 | `RulesToggle` 自畫展開鍵（`+`/`−`）；規則一格一個 `×` 的樣式 DESIGN.md 還沒記 | 後續票已處理 | M3 票 21（`/impeccable document` 寫進 DESIGN.md，「Known contradiction」）；字元圖示的不一致仍記為已知矛盾 | 否 |
| M3 票 10 | 三支 `set_*exclusions` 收緊時擋下的放不回來，因此沒有單一反向命令（已改為不宣告 `inverse`） | 仍未處理 | `berth/services/rss.py` 的 `set_*exclusions` 標 `REVERSIBLE` 而無 `inverse`（同 13/19 同類）；`_rescreen` 註解「只收緊：擋下的不放回來」`:1624` | 是：登錄表要決定「可逆但無單一反向」的命令能不能給 AI（plan §11.6） |
| M3 票 11 | `prime_feed(later)` 裡的輪詢與背景 poller 同寫同一批 guid 撞 `(feed_id, guid)` unique 冒 500；要 `INSERT … ON CONFLICT DO NOTHING` | 仍未處理 | `berth/services/rss.py:1052-1100` `_record` 仍 `session.add(RssItem…)` + `flush`，未見 `on_conflict`；§11.4 延後 | 否 |
| M3 票 11 | 預覽沒有叫 `_sent_before`，刪掉 Feed 再加回來時預覽說「重複」，送單時認回已送單 | 仍未處理 | `berth/services/rss.py:1408` `_sent_before` 只在送單路徑（`:1351`）；未見預覽呼叫 | 否 |
| M3 票 11 | 「全部下載」不重讀 feed，預覽到確認之間 poller 新寫入的幾筆一起送，確認區數字可能少算 | 仍未處理 | 票 21 歸「刻意的行為」；`prime_feed`（`berth/services/rss.py:770`）未重讀 | 否 |
| M3 票 11 | 讀不出組名的發佈鍵尾是空的，兩個都沒組名的上傳者同一部作品會併進同一個 Series | 仍未處理 | 未見後續票；票 21 歸「沒有 repro」 | 否 |
| M3 票 11 | 切集號的 `_TITLE_END` 是新寫的一份，與解析器既有規則形狀不同 | 仍未處理 | `berth/parser/binding.py:50`、`:116` | 否 |
| M3 票 11 | 來源分支散在五處，加第四站（dmhy、generic）時一起收成一張表 | 仍未處理 | `berth/services/rss.py:167-173`（`_NO_PREVIEW`）、`:1009`、`:1122`、`:2579`；沒有第四站，故未觸發 | 否 |
| M3 票 11 | `rss_items.torrent_url` 有時存 magnet，欄位名沒改 | 仍未處理 | `berth/models/rss.py:153` `torrent_url` | 否 |
| M3 票 11 | 「只追之後的」之後，只有擋下與略過 Item 的 RSS Series 仍在待綁定、寫「留著 0 集」；留給 M3 收尾 critique | 仍未處理 | 票 21 critique 列為 P2「`全部下載` 在會送出 0 時名實不符」不修；歸「不做」 | 否 |
| M3 票 11 | 前端 `Group` 每一列與「最近的 Feed Item」列形狀相近，沒抽共用元件 | 仍未處理 | 判斷題；未逐檔重驗 | 否 |
| M3 票 12 | `_record` 仍有 `known=` 一個模式參數（拆兩支會重複整段寫 Item） | 仍未處理 | `berth/services/rss.py:1052-1058` `_record(... keys ...)` 模式參數仍在（未逐一重驗 `known`） | 否 |
| M3 票 12 | 補漏的失敗與輪詢的失敗拼在同一個 `last_error`，要分時（M4 通知）再拆欄 | 後續票已處理 | M4 票 130：`berth/models/rss.py:56` `poll_error`、`:62` `backfill_error`；plan §11.5「票 130 做完」 | 否 |
| M3 票 12 | 綁過的 Series 季末之後仍每天讀一次單一 feed，請求量隨綁過的部數線性長，預算在票 20 統一 | 後續票已處理 | M4 票 108（完結不補）、116（完結後補最後一次）、107（預算整個刪掉）；progress.md 偏差「2026-10-19 M4 票 108」 | 否 |
| M3 票 12 | 使用者自己把單一 feed 加成 Feed：`passed_before` 不作用在它身上，同一集在兩個 Feed 下各一筆 | 仍未處理 | 票 21 歸「刻意的行為」；`berth/services/rss.py` `passed_before` 只在補舊集路徑 | 否 |
| M3 票 13 | 跟著重算的集數由 rematch 另建單列 Plan，沒記 `rss_series_id`/`season_hint`/`episode_offset` | 仍未處理 | 票 21 歸「沒有 repro」；`berth/services/series_review.py` 的 `_carry` 仍走 rematch 單列 Plan | 否 |
| M3 票 13 | 逐列按「確認」不會把 Series 標成確認過，只有組與整段「全部確認」會；第一批確認完之前新進集數仍是第一批 | 仍未處理 | 票 21 歸「刻意的行為」；`berth/api/review.py:329` `confirm_audit` 與 `:343` `confirm_audits` 不碰 Series，`confirm_series`（`:61`）另一支 | 是：AI 任務「audit 的確認或撤銷」，逐列確認不標 Series 與整組確認語意不同，登錄表輸入要分清 |
| M3 票 13 | `QUEUE_LIMIT`（200 列）截斷時，組上「全部確認」只確認畫面上那幾列，Series 卻整個標成確認過 | 仍未處理 | `berth/services/review.py:85` `QUEUE_LIMIT = 200`；§11.4 延後（`docs/plan.md:965`） | 是：AI 批次確認若走同一支命令會重現 |
| M3 票 13 | offset 以檔名集號算（`parser.written_episode`），規劃器帶季號提示時仍對 `Part N` 套 cour 換算，三 cour 以上或帶 `Part N` 的 Series 可能多算一截 | 仍未處理 | `berth/services/series_review.py:53`、`:162` 使用 `written_episode`；票 21 歸「沒有 repro（`Part N` 多算）」 | 是（弱）：AI「季號與 offset 修正」任務的驗證要覆蓋 |
| M3 票 13 | 判斷題：`trigger_ref` 就是 Series id 有三份寫法；`Landing.because/audit` 是 `Assignment` 複本；`Plan.season_hint` 對 `RssSeries.season` 兩個名字；`AuditSeries.name` 裝 `title_raw`；整段確認由前端拆；`seriesValues.ts` 消費者都不在 rss 頁 | 仍未處理 | 票 21 歸「判斷題票上已結」；`berth/services/plan.py`、`review.py`、`series_review.py` 仍各自 cast（未逐項重驗） | 否 |
| M3 票 13 | `correct_series`/`confirm_series` 標 `reversible`、`inverse=None` | 仍未處理 | `berth/services/series_review.py` 兩支命令仍 `inverse=None`（票內已寫理由於 docstring） | 是：AI 任務「RSS Series 的季號與 offset 修正」直接呼叫；登錄表要決定可逆但無反向的處理（plan §11.6） |
| M3 票 14 | 網路先行配信（ABEMA、Netflix 比電視早一週，TMDB 記電視日）會被規則一擋 | 仍未處理 | 票 21 歸「沒有 repro」；`berth/parser/airing.py` 規則一未變 | 是（弱）：AI 結果與人都過同一條播出日比對（plan §11.4 ①） |
| M3 票 14 | 核准被擋的列時不再比帳本：`_duplicate_of` 只比 `import` 的列，`promote` 後直接入庫，`span_clash` 會漏 | 仍未處理 | §11.4 延後（`docs/plan.md:965`）；`berth/services/plan.py:709` 只在規劃時比、核准步驟（`plan_review.py`）未再比 | 是：M5 驗證要求「不撞目標路徑、季集範圍」，AI 結果核准路徑會踩到同一縫 |
| M3 票 14 | 字幕跟著被擋的影片時仍是 `subtitle`，整份停在 `pending_review`，畫面上一對狀態不一致 | 仍未處理 | 同 `_apply_policy` 既有行為；票 21 歸判斷題 | 否 |
| M3 票 14 | split-cour 播出日產生器有三份（兩個測試檔、`fake_setup_server`） | 仍未處理 | 判斷題，合併要跨 `scripts/` 與 `tests/`；票 21 歸判斷題 | 否 |
| M3 票 14 | `_latest` 回傳 `tuple[tuple[int,int], date]`、`_airing` 用 `source_url` 判斷有沒有來源 | 仍未處理 | 判斷題，`berth/parser/airing.py` 未見調整 | 否 |
| M3 票 14b | 被改的那一份核准之後，跟著重算的列不在第一批裡（`plan._audit` 只看 `auto`） | 仍未處理 | `berth/services/plan.py:947-959` `_audit` 判斷；維持的決定（票內寫明） | 是（弱）：第一批審核與 AI audit 任務的範圍界線 |
| M3 票 14b | `held_proposal` 不比帳本（重複版本、範圍衝突），與票 14 同一個縫 | 仍未處理 | §11.4 延後；`berth/services/plan.py:217` `held_proposal` | 是：同票 14 |
| M3 票 14b | 守門與 offset 計算和 `correct_series` 幾乎一樣、只差例外型別；`PlanRefusal`/`RematchRefusal` 各有 `not_from_series`/`no_episode_number` 兩份文案；`SeriesCorrected`/`HeldSeriesCorrected`/`SeriesCorrectedOut` 三份五欄位 | 仍未處理 | `berth/domain/enums.py:1486`、`:1529` 兩個 `NOT_FROM_SERIES`；`berth/api/files.py:50`、`berth/api/plans.py:67` | 否 |
| M3 票 14b | 拒絕文案寫死勾選框的標籤；改過之後那一份在佇列上仍說「發佈時間與換算出的集數的播出日對不上」 | 仍未處理 | 判斷題；`_write` 留著 `review_reason`（票內決定）；未逐項重驗文案 | 否 |
| M3 票 14b | `correct_series_from_plan` 標 `@command(Effect.REVERSIBLE)` 且反向命令同 `correct_series`：沒有 | 仍未處理 | `berth/services/series_review.py`（`correct_series_from_plan`）`inverse=None` | 是：同 13，可逆但無反向命令 |
| M3 票 15 | 每集短於 5 分鐘的短篇動畫被 `classify` 整包降成 extra，註解說的「批次一致性救回」並不存在 | 仍未處理 | `berth/parser/classify.py:80` `SHORT_FEATURE = 300`、`:144`；§11.4 延後（可改看 TMDB 片長） | 否 |
| M3 票 15 | 電影的片長在 `MediaSnapshot.runtime`，片長驗證只做劇集的集 | 仍未處理 | `berth/parser/runtime.py` 只比集；票內寫明沒做 | 否 |
| M3 票 15 | mediainfo 替身在整合測試與 `fake_setup_server.py` 各寫一份；`runtime_gap.py` 沒用 `lib.py` 的 `request` | 仍未處理 | 判斷題，票內說明刻意不共用；`scripts/experiments/runtime_gap.py` | 否 |
| M3 票 15 | 與正片一樣長的番外被當成正片，片長驗證看不出來（已知盲點）；TMDB `runtime` 為 `null` 約 46.6%，`runtime_missing` 常見 | 仍未處理 | `berth/parser/runtime.py:33-40`（`RUNTIME_SLACK=180`、`RUNTIME_RATIO`）；plan §4.2 已寫為盲點 | 是（弱）：AI 任務「三道程式檢查標出的可疑入庫」的輸入就是這些漏網與 `runtime_missing` |
| M3 票 16 | 票 16 的「以發佈時間推測虛擬季」偏離票面兩處（只推「剛播」的一輪、只套到篇章名），使用者還沒追認 | 仍未處理 | §11.4 延後（`docs/plan.md:965`）；progress.md「2026-09-26 M3 票 21：票 16 的規則偏差使用者先不追認」；`berth/parser/mapping.py:580-591` `_published_run` | 是（弱）：規則層 low 的 Plan 是 AI 任務的觸發條件，推測誤差影響觸發量 |
| M3 票 16 | 「推測錯了由驗證擋下」只成立在邊角，主要靠 medium 的 audit 與第一批審核 | 仍未處理 | plan §4.4 已照實寫；`berth/parser/mapping.py:591` 注解 | 是（弱）：同上，AI audit 確認的負擔 |
| M3 票 16 | `_published_run` 內部重算 `len(_runs(media))`；`media, info, span, check` 一起傳是模組既有形狀 | 仍未處理 | 判斷題；`berth/parser/mapping.py:580` | 否 |
| M3 票 16 | 前端 UI 沒用 playwright 實跑（`published_in_run` 理由句、策略名、audit 收起原因），要有 TMDB 併季演練情境才看得到 | 仍未處理 | 票內明寫未做；`web/src/review/leadReason.ts:25` 已有 `published_in_run`；未見併季演練情境 | 否 |
| M3 票 17 | 「重新反查」按下去那一件就由使用者收掉，之後仍不一致才開新的一件；要等比完才收得讓 `resolve_issue` 有「送出之後仍開著」的動作 | 仍未處理 | 票內「另議」；`berth/services/issues.py:319` `resolve_issue` 未見該動作 | 是：Issue 動作逐顆標（plan §11.6）時要定 `relook` 的語意 |
| M3 票 17 | 「忽略」之後第二天對帳又開，應沿用「條件持續期間忽略有效」 | 後續票已處理 | M4 票 122：`berth/services/issues.py:989-997` `STAYS_IGNORED` 含 `JELLYFIN_ITEM_MISMATCH`；plan §11.5 | 是：「忽略 Issue」在 M5 是 Proposal（plan §11.6），其語意就是這條 |
| M3 票 17 | `services/issues` 仍在 `BEFORE_M3` 豁免表，`resolve_issue` 沒有標記，M5 做登錄表時逐顆動作標（`ACTION_DELETES` 旁邊） | 仍未處理 | `tests/unit/test_command_marks.py` 的 `BEFORE_M3`（41 個模組）仍含 `"issues"`；`berth/services/issues.py:319` `resolve_issue` 無 `@command` | 是：plan §11.6 點名「`services/issues` 仍在豁免表」 |
| M3 票 17 | `detail_json.differs` 三個值（`season`/`episode`/`tmdb`）是裸字串，前端 `IssueRow.tsx` 的 `DIFFERS` 抄一份 | 仍未處理 | `berth/services/resolver.py:311-318`；`web/src/issues/IssueRow.tsx:371` | 否 |
| M3 票 17 | `TMDB 120089` 的前綴直接寫在 JSX，機器字串不翻譯 | 仍未處理 | 刻意決定（票內寫明） | 否 |
| M3 票 18 | `read_oneshot` 不檢查 Route 收不收得下這部作品、停用與否（`route_kind_mismatch`/`route_disabled`） | 仍未處理 | `berth/services/oneshot.py:84-99` 只查 `route_missing`；`check_route` 在 `berth/services/jobs.py:944` 於送單時擋 | 否 |
| M3 票 18 | `OneshotSection.WorkPicker` 與 `SeriesBinder` 搜尋區仍重複（防抖、`titleOf`/`aboutOf`、錯誤句子） | 仍未處理 | `web/src/rss/OneshotSection.tsx`、`SeriesBinder.tsx` 仍各一份；`WorkChoices.tsx` 只抽 `Choices` | 否 |
| M3 票 18 | `oneshot._item` 單集 `episode_end` 補成起始集，與 `search.estimate` 同一條規則各寫一次 | 仍未處理 | `berth/services/oneshot.py`（`_item`）與 `berth/services/search.py`；判斷題 | 否 |
| M3 票 18 | 每一筆各打一次 `library_copy`（N+1） | 仍未處理 | `berth/services/oneshot.py:156`；票內「feed 通常幾十筆，先不動」 | 否 |
| M3 票 18 | 檔名 `WorkChoices.tsx` 匯出的是 `Choices` 與 `Pickable` | 仍未處理 | `web/src/rss/WorkChoices.tsx` | 否 |
| M3 票 18 | 「勾選全部單集」鍵票面沒要求（小幅擴張） | 仍未處理 | 記錄項，非缺陷；`web/src/rss/OneshotList.tsx` | 否 |
| M3 票 19 | `media/SubscribePanel.tsx` 的 `Options<T>` 與 `rss/WorkChoices.tsx` 的 `Choices` 同形；「資料夾名將定下來」那兩行是第三份 | 仍未處理 | `web/src/media/SubscribePanel.tsx`、`web/src/rss/WorkChoices.tsx`；判斷題 | 否 |
| M3 票 19 | `_series_view` 每一列多兩個查詢，`/rss` 的 Series 清單是 N+1 | 仍未處理 | `berth/services/rss.py` `_series_view`；票內「幾十個量級」；M4 票 13 重做 RSS 頁，未見改查詢 | 否 |
| M3 票 19 | `subscribe_search` 依 `FeedKind` 分派到 adapter 是 `rss.py` 第三處 `match kind` | 仍未處理 | `berth/services/rss.py:2579`（`match kind: case FeedKind.NYAA/ACGRIP/MIKAN`） | 否 |
| M3 票 19 | 預先綁定的 Feed 帶到已綁在別部作品上的同鍵 Series 時不改綁（人或自動綁定做過的決定） | 仍未處理 | 刻意行為，票 21 歸「刻意的行為」；`berth/services/rss.py` `_prebind`（`:1650` 後） | 否 |
| M3 票 19 | `subscribe_mikan` 就地綁定那條的反向命令不是 `delete_feed`（改成不宣告單一反向） | 仍未處理 | `berth/services/rss.py` `subscribe_mikan` 標記無 `inverse`；票內已修標記，但「可逆而無單一反向」仍待登錄表處理 | 是：同 10/13，可逆無單一反向（plan §11.6） |
| M3 票 20 | 「照預算分批問完」解讀成下一批由人按，不是背景自動問完 | 已不適用 | M4 票 107（brief §19 2026-10-19）推翻 M3 票 20 的請求預算；批次提示仍保留（`berth/services/search_queries.py:126` `missing_batches`）但不再依預算，由人按下一批 | 否 |
| M3 票 20 | Torznab 端點不和 RSS 共用預算；`.torrent` 下載不在預算裡；沒做每秒節流與 429 逐級退避 | 已不適用 | M4 票 107：`berth/adapters/budget.py` 已刪（不存在）；M4 票 37 同時拿掉通用 Torznab | 否 |
| M3 票 20 | 作品名搜尋與 `/rss` 上人按的讀取也吃同一份預算（範圍外但做了） | 已不適用 | M4 票 107 刪預算；`GET /health/budget` 與 `BudgetCard` 皆已移除 | 否 |
| M3 票 20 | `services/health.read_budget` 只是轉手；`RequestBudget` 放在 `adapters/` | 已不適用 | `grep read_budget\|RequestBudget berth` 0 筆（M4 票 107） | 否 |
| M3 票 20 | 三者共用的整合測試用綁定時補舊集，每日補漏被擋在另一條測試；`feed_fetcher` 閘門 `test_feed_fetcher_gate.py` | 已不適用 | M4 票 107：`tests/unit/test_feed_fetcher_gate.py` 已刪（`ls` 不存在），progress.md 偏差記「回到沒有閘門」 | 否 |
| M3 票 21 | 票 16 的規則偏差使用者先不追認，記在 plan §11.4 結尾延後清單 | 仍未處理 | 同票 16 首列：`docs/plan.md:965`；progress.md「2026-09-26 M3 票 21」 | 是（弱）：同票 16 |
| M3 票 21 | 一次送近兩百個 torrent 時 `GET /api/v2/torrents/categories` `ReadTimeout`，一筆停在 `submit_failed`，poller 認回接不到 | 後續票已處理 | M4 票 03：暫時失敗由 poller 自動重送（`berth/services/jobs.py:560-600` 一輪遇到第一筆又失敗就收手）；plan §11.5「票 03 已做」 | 否 |
| M3 票 21 | 票 15 的 payload：片長驗證讓 M1 三包 `.mkv` 標頭要照 TMDB 快照寫片長；迷你特典「分類器與片長驗證沒有一致答案」（plan §11.4 結尾延後） | 仍未處理 | `docs/plan.md:965` 同「短篇動畫降 extra」那條；`tests/e2e/payload.py` 的 `lasting` | 否 |
| M3 票 21 | critique P2：待綁定列的標題是最新一集的發佈名、來源欄印 id | 已不適用 | M4 票 13（`web/src/rss/seriesByWork.ts`、`SeriesSection.tsx`）改成以作品呈現 Series；逐項未重驗來源欄 | 否 |
| M3 票 21 | critique P2：待綁定與 Plan 沒有批次操作 | 仍未處理 | 票 21 歸「不做」；`/review` 與 `/rss` 待綁定仍逐列 | 否 |
| M3 票 21 | critique P2：每列待綁定 3 個 Tab 停留點 | 已不適用 | M4 票 13 重做待綁定段；未重驗 Tab 停留點數 | 否 |
| M3 票 21 | critique P2：`/review` 的 Plan 沒有依 RSS Series 分組、「套用到這個 RSS Series」沒重述範圍 | 仍未處理 | 票 21 歸「不做」；§11.5 遺留未再提；`web/src/pages/ReviewPage.tsx` 未見 Series 分組（未逐項重驗） | 否 |
| M3 票 21 | critique P2：預算原文沒本地化 | 已不適用 | M4 票 107 刪預算 | 否 |
| M3 票 21 | critique P2：回驗不符的「下一步」沒依不同之處挑修法 | 仍未處理 | 票 21 歸「不做」；`web/src/issues/IssueRow.tsx`（`DIFFERS` 只決定強調哪一格） | 否 |
| M3 票 21 | critique P2：「全部下載」在「會送出 0」時名實不符 | 仍未處理 | 票 21 歸「不做」；`web/src/rss/FirstRoundSection.tsx` 未重驗 | 否 |
| M3 票 21 | critique P2：一次性連結的搜尋預填取第一筆 | 仍未處理 | 票 21 歸「不做」；`web/src/rss/OneshotSection.tsx` 未重驗 | 否 |
| M3 票 21 | audit P2：手機上 GhostButton 35px 高、`COMPACT_BUTTON` 24px（過 AA 下限、低於 44px） | 仍未處理 | `web/src/components/controls.tsx:215-216` | 否 |
| M3 票 21 | audit P2：JS 一個 898 KB 的 chunk、i18n 兩種語言整包送 | 仍未處理 | `grep lazyRouteComponent web/src` 0 筆（同 06 路由拆分） | 否 |
| M3 票 21 | audit P2：`/review` 12 列 article 的可存取名稱都是作品名 | 仍未處理 | 票 21 歸「不做」；未重驗 | 否 |
| M3 票 21 | audit P3：勾選框本體 16px | 仍未處理 | 票 21 歸「不做」；未重驗 | 否 |
| M3 票 21 | audit P3：預算「6 / 6」沒有已用/上限的語意 | 已不適用 | M4 票 107 刪預算與 `BudgetCard` | 否 |
| M3 票 21 | audit P3：訂閱失敗的原文是 UTC 微秒時間 | 仍未處理 | 票 21 歸「不做」；未重驗 | 否 |
| M3 票 21 | audit P3：390 上頁首導覽佔 34% | 仍未處理 | 票 21 歸「不做」；未重驗 | 否 |
| M3 票 21 | code-review：`FeedRoutePicker` 與 `media/RoutePicker` 外框重複 | 已不適用 | `grep FeedRoutePicker web/src` 0 筆；M4 票 105 重做 Feed 的 Route 選擇（`web/src/rss/feedRoutes.ts`） | 否 |
| M3 票 21 | code-review：`_pin_jellyfin` 與 `indexer._pin_probe` 只差種類 | 已不適用 | 兩函式已不存在（`grep _pin_jellyfin\|_pin_probe berth` 0 筆；M4 票 15 移除偵測） | 否 |
| M3 票 21 | code-review：`library_count` 在兩張卡各畫一次 | 仍未處理 | `web/src/health/HealthBoard.tsx:61`、`web/src/health/ServiceCard.tsx:58` | 否 |
| M3 票 21 | code-review：`PollOut.failed` 是字串（同 `PollOutcome.failed` 與 `last_error`） | 仍未處理 | `berth/services/rss.py:372` `failed: str = ""` | 否 |
| M3 票 21 | code-review：RSS 站主機名散在四處（e2e 基礎設施） | 仍未處理 | `grep mikanani.me` 命中 `berth/adapters/rss/mikan.py`、`berth/domain/enums.py`、`berth/services/rss.py:167`、`tests/e2e/sites.py`、`tests/e2e/compose.yml` | 否 |
| M3 票 21 | 開工時發現：票 15 之後真服務 e2e 紅，因票 15 那輪只跑 `pnpm -C web e2e` 沒跑真服務 e2e | 後續票已處理 | M3 票 21 修 `payload.py`；M4 票 133 / plan §11.5 要求驗收跑真服務 e2e；nightly 與 CI `e2e.yml` 持續守 | 否 |
