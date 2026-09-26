# 04 — 下載列表分頁與 SSE 失效合併

**Status:** ready-for-agent

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

- [ ] 500 筆 Job 時 `/jobs` 第一頁的回應大小與筆數有上限（整合測試）
- [ ] 一秒內 20 個 SSE 事件只造成一次清單重抓（vitest，雙向：單一事件仍會重抓）
- [ ] 刪除對話框開著時，別的 Job 的事件不讓估算重跑（vitest）
- [ ] playwright 實跑下載列表：翻頁、篩選、即時更新仍會動，1280 與 390 各一份截圖或文字結果
- [ ] lint、type、test、前端 e2e 綠燈

## Comments
