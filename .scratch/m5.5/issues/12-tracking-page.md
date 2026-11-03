# 12 — 追更頁

**Status:** done

**Blocked by:** 09, 11

**讀:** spec〈範圍〉「追更頁」「新番區塊」；brief §13；plan §7；ADR-0015；`domain.WhyNot`；`GET /me/notifications`；`.scratch/m5.5/schedule-shape.md`

## 為什麼

管理員要一眼看出訂閱的作品哪些按時、哪些晚了、卡在哪。沒接 Discord 的管理員只能從這一頁知道有遲到。

## 做什麼

1. **先 `/impeccable shape`**：輸出 `.scratch/m5.5/tracking-shape.md`。
2. **`/schedule/tracking`**（admin，新番區塊的「追更」分頁，排在時間表與訂閱之間）：依作品一列，欄位為字幕組、已播到、已入庫到、狀態。
   - 狀態是 `domain.WhyNot` 的結論，加「晚 N 天」與「可能是下一輪」（11 的 `next_run`）。
   - **下載停滯要說出來**：`WhyNot` 把 `stalled` 算成 `DOWNLOADING`，這一頁另外顯示「下載停滯」。
   - 排序：要人動手的在前，準時的在後，「斷更很久」（11 的 60 天視窗）收起。
   - 讀取命令 `Effect.READ`，端點進 `ADMIN_PREFIXES`，`TestWhoEachEndpointIsFor` 補一列。
3. **收不到通知時頁首說一句**：這位管理員沒有 bot、沒填 Discord ID、沒訂閱「等你處理」或 Discord 到不了時，提示遲到只會顯示在這裡、不會通知，連到 `/settings/notifications`。讀 `GET /me/notifications` 就夠，不加端點，不另做其他通知管道（ADR-0015）。
4. **時間表卡片**多「晚 N 天」狀態（只有 admin 看得到字幕組相關的部分，比照 09）。
5. 文件：brief §13、plan §7 路由表、`CONTEXT.md`（追更）。
6. **區塊設定收成一份**（票 07 code-review 留下、票 09 轉來）：一個區塊的連結、頁面清單、分頁與件數現在散在 `nav/sections.ts`、`SectionLink` 的 `to` 型別、`SectionTabs`、`AppShell` 四處；加「追更」分頁時收成一個區塊物件，加一頁只改一處。

## 驗收

- [x] 追更頁把停滯顯示成「下載停滯」，不是「下載中」；「斷更很久」預設收起（e2e，桌機與 390px）
- [x] 沒接 Discord 時追更頁頁首有提示；收得到通知的管理員看不到提示（e2e 或 vitest）
- [x] `/schedule/tracking` 對一般使用者 403 或導向（`TestWhoEachEndpointIsFor`＋e2e）
- [x] 時間表上晚了的卡片顯示「晚 N 天」
- [x] 全部檢查、pytest、vitest、前端 e2e 綠；progress.md 已更新

## Comments

- 2026-11-04 shape（`.scratch/m5.5/tracking-shape.md`）使用者定兩件：**「晚 N 天」從播出日算**（10/28 播出、10/31 寫「晚 3 天」，與門檻無關）；**桌機表格、窄版一部一塊**。時間表卡片的「晚 N 天」是中性色塊（一般使用者也看得到、動不了手）。
- 後端模組叫 `services/keeping_up.py`（`CONTEXT.md`「Keeping up（追更）」）：`services/tracking.py` 已經是 Tracked Media，網址照票留 `/schedule/tracking`。
- 判定與巡檢同一套：`parser.overdue.watch_overdue` 回 `Watch`（缺的集、晚的集、過了視窗沒），巡檢取 `.overdue`；`keeping_up.watched_works`、`watch_work`、`watch_of` 從 `sweep` 搬出，`_covered` 改成 `issues.covered_jobs`。「下載停滯」的規則在 `domain.stalled`；每集結論是 `why_not.account_missing`（同 `explain` 的「誰蓋到哪一集」）。
- 區塊設定收成 `web/src/nav/sections.ts` 的 `Section` 物件（分頁、誰看得到、帶哪一格件數），`SectionLink` 與 `SectionTabs` 都讀它；加一頁改那裡加 `routes.tsx` 的路由。`/schedule/tracking` 在 `/schedule` 底下，分頁與頁首那一項改用 `exact` 比對。
- fake 情境 `tracking`（`docs/development/fake-backend.md`），e2e `tracking` / `tracking-390`（8502 / 8503）。e2e 文件的流程數原本少算了時間表（票 09），一起改成二十六條、四十八個 project 並補時間表那一列。
- playwright 實跑：`tracking` 情境 1440 與 390，三段、停滯寫「下載停滯」、斷更很久收起與展開、頁首提示都對；欄名與值改成基線對齊。impeccable detect 0 件。`berth bench` auto_wrong 0 → 0（`parser/overdue.py` 不在解析管線上，照共同規則跑）。
- code-review 已處理：`judge_overdue` 沒有正式呼叫端了，刪掉、測試改走 `watch_overdue(...).overdue`；時間表的天數改用遲到判定看到的播出日、時鐘只用時間表那一支（`late_by_work(now=...)`）；巡檢與時間表共用 `watch_of`、作品分組只在 `watched_works` 一份；`late_by_work` 一部讓出一次迴圈；`why_not` 抽 `_jobs_of`；待處理誰看得到改由 `SectionLink` 照區塊判斷；追更自己的分隔字 key；季中訂閱、之後沒有新的一集時原本寫「還沒播」，改成「跟上了」（先寫會紅的測試）。
- code-review 未處理（判斷題）：
  - `TRACK_ITEM_SCAN = 60`：追更頁每部只猜最近 60 筆 Feed Item（作品頁 500）。缺的是最新的集、蓋到它們的是最近的 Item；更舊的 `matched` / `unbound` 落在 60 筆外時，那一集在這頁說「字幕組還沒發」、作品頁說「下載中」。不影響晚不晚（只看 Job）。一頁二、三十部全猜 500 筆，冷快取會慢到十幾秒。
  - 一集停滯、另一集還在下載時，狀態只寫「下載停滯」（整部排進要你動手是對的，文字沒說另一集在動）。
  - 「沒有快照」靠 `conclusion === null` 表示，沒有另一個欄位；API 文件寫明了。
  - 「容器時區的現在」有 `reconciling.local_now`、`schedule.local_today`、`keeping_up.local_now` 三份，各自給測試換；收成一支是另一張整理票的事。
