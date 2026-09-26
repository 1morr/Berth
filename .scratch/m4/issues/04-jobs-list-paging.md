# 04 — 下載列表分頁與 SSE 失效合併

**Status:** done

**Blocked by:** None — can start immediately

**讀:** plan §11.5「M4 之前先做的修補」、§6（jobs 群組）、§7（前端資料與即時更新）；brief §13（下載列表）；`.scratch/m1.5/issues/09-long-lists.md`（媒體庫分頁的慣例）；進 UI 前 `/impeccable shape` 下載列表的分頁與篩選

## 為什麼

`GET /jobs` 回整張表（`berth/services/jobs.py:550-554` 沒有 limit、沒有篩選），`_plans_of` 的
`Plan.job_hash.in_(...)`（`:955-961`）也沒分塊。這條 2026-09-22 在 progress.md 記「歸票 12」，之後沒有任何
票或 plan 條目接手（2026-09-26 全面審查的遺留帳本裡唯一真正漏掉的一條）。

RSS 無人值守讓 Job 快速累積：2026-09-26 試跑一次綁定就送 144 筆，完成的也不會離開清單。前端每收到一個
SSE 事件就讓整個 `['jobs']` 前綴失效（`web/src/api/events.ts:36-40`），poller 下載中每 5 秒、每筆有變動的
Job 各推一個事件，所以一批 N 個事件是 N 次完整的 `GET /jobs`（`apiGet` 沒接 `signal`，被取消的請求照樣送到
後端）。同一個前綴還涵蓋刪除估算 `['jobs', hash, 'deletion']`（`web/src/api/jobs.ts:152`，每次重跑逐檔
`stat`）與 Plan `['jobs', hash, 'plan', id]`（`web/src/api/plans.ts:72`）。

## 做什麼

1. `GET /jobs` 分頁與狀態篩選（預設把已入庫的與需要人的分開，形狀照媒體庫的長清單慣例）；`_plans_of`
   不再吃無上限的 `in_()`。
2. SSE 失效合併：短時間內的多個事件只失效一次（`cancelRefetch: false` 加節流），`apiGet` 接上 `signal`。
3. 刪除估算的 query key 移出 `['jobs']` 前綴（它不該被別的 Job 的進度刷新）。
4. `pnpm gen:api` 同一個 commit。

## 驗收

- [x] 500 筆 Job 時 `/jobs` 第一頁的回應大小與筆數有上限（整合測試）
      —— `test_jobs_api.py::TestTheList::test_five_hundred_jobs_answer_one_bounded_page`：50 筆、約 29 KB（上限斷言 64 KiB；
      不分頁的一整份約十倍）。`_plans_of` 的 `in_()` 因此最多一頁；服務層另測四組篩選、件數與翻頁（`TestTheListIsPagedAndFiltered`）。
- [x] 一秒內 20 個 SSE 事件只造成一次清單重抓（vitest，雙向：單一事件仍會重抓）
      —— `api/events.test.tsx`：掛真的 query、數 `fetch` 次數（修之前 4 條紅）。另兩條：清單或那一筆的詳情還在抓時到的推播
      等它回來再重抓（code-review 抓到 hash 鍵沒守，改完先確認舊寫法會紅）。
- [x] 刪除對話框開著時，別的 Job 的事件不讓估算重跑（vitest）
      —— 同一個檔案；估算的 key 改成 `['deletion', hash]`。
- [x] playwright 實跑下載列表：翻頁、篩選、即時更新仍會動，1280 與 390 各一份截圖或文字結果
      —— 演練情境 `import` + 直接寫進 105 筆 Job。1280：篩選「在路上 3 · 需要人 3 · 已入庫 100 · 全部 120」、`已入庫` 翻到第 2 頁
      （`51–100 / 100`、下一頁 `aria-disabled`、清單底另一組）、鍵盤 Tab 到「需要人」Enter 換組。即時：從作品頁送單 →
      `/jobs` 上「已送出 → 下載完成」→ 入庫那一刻離開在路上、「已入庫」變 101（3.3 秒），這段期間清單只重抓兩次、間隔 ≥ 1 秒。
      390（中英兩種）：頁面層級橫向捲動 0，清單底的「下一頁」可用。截圖 `.playwright-mcp/t04-*.png`（不進版控）。
- [x] lint、type、test、前端 e2e 綠燈
      —— 前端 e2e 31 條過 29；紅的兩條是 `rss-subscribe`（兩種寬度），**本票之前就紅**：在 HEAD 的 worktree 上同一條
      一次綠一次紅（見 Comments）。其餘指令輸出在 progress.md 同日那一行。

## Comments

- **`rss-subscribe` 的 e2e 是既有的時序 flake，不是本票**：acg.rip 搜尋 feed 建好之後 `GET /rss/feeds/{id}/preview` 5 秒內沒回來，
  那時後端正在規劃 Mikan 補舊集的 12 筆（每筆約 0.5 秒，一個接一個）。乾淨的 HEAD（`3522046`）worktree 跑同一條：一次綠、
  一次紅。沒修：不在這張票，要修的話是另一張（預覽的讀取被規劃器餓死，或 spec 等久一點）。
- **在「在路上」看著的那一筆入庫時會從清單消失**（shape 已寫明的代價）：鍵盤焦點若正停在那一列會掉回 `body`——
  `useFocusAfterRemoval` 認的是 `<article>`，下載列是 `<details>`。沒做。
- code-review 留著沒改的（判斷題）：
  - `?page=1e20` 過得了前端的驗證，SQLite 的 offset 溢位回 500，畫面說「後端不可達」。媒體庫的牆是同一種寫法。
  - 兩個 `PAGE_SIZE`（jobs 與 inventory）是同一個數但各自一份：它們是兩張清單的慣例值，沒有必須一起變的理由。
  - `JobsPager` 與 `WallPager` 的 `announce` 那一段形狀相同（兩組 i18n 鍵），預設篩選 `'active'` 在前端有幾處字面值、
    `list_jobs(shown=)` 的參數名。
  - `onOpen` 仍取消進行中的請求（票 10 的理由，註解寫了），每次進頁多一個被取消的請求。
  - 同檔的 `_due_retries` 對全部 `submit_failed` 做 `in_()`，票沒要求。
