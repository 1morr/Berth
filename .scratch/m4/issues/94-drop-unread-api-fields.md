# 94 — 簡化：刪掉前端沒讀的 API 回應欄位

**Status:** done

**Blocked by:** None — can start immediately

**讀:** `docs/research/simplification-audit-2026-10-13.md` 的 S32；`docs/plan.md` 的 API 段（`plan.md:402`、`plan.md:404`）

## 為什麼

票 86 審計逐欄搜過 `web/src` 與 `web/e2e`，下面這些回應欄位一個讀取點都沒有。留著會讓人以為有人在用，改的時候還得顧著它們。使用者（2026-10-13）照協調者建議：刪掉清單上的欄位，留兩組。

## 做什麼

- **刪**（只從 `*Out` 拿掉；services 的欄位與資料庫不動）：
  - `DeletionEstimateOut.link_bytes`、`source_bytes`
  - `JobOut.route_slug`、`trigger_ref`、`user_id`、`completed_at`、`imported_at`
  - `BudgetOut.window_seconds`、`SiteBudgetOut.frees_at`、`DeferralOut.since`
  - `ItemOut.seen_at`、`BangumiOut.premiere`、`UnmatchedRowOut.file_kind`
- **留**：
  - `JobOut.content_path`：真實服務的 e2e 靠它找檔案。
  - `PlanOut.engine`、`engine_version`：M5「AI 提案還是規則提案」會用到。在 plan 的 API 段寫一句為什麼留。
- 刪欄位之後，services 端如果有只為了這些欄位而算的東西，一併拿掉；有別的讀者的留著。

## 驗收

- [x] 上列欄位已從回應拿掉；`gen:api` 重跑；後端斷言與前端 fixture 跟著改（審計列了位置）
- [x] 留下的兩組在 plan 寫明理由
- [x] plan 的 API 段（`GET /health/budget` 的「放得下的時刻」、番組的 `premiere`）同步；CHANGELOG 記在 Removed（對外 API 回應形狀變了）
- [x] 全部檢查、pytest、vitest、前端 e2e 綠；progress.md 已更新

## Comments

- 2026-10-13 收尾 code-review（Standards、Spec 兩軸）唯一的發現是 plan 的 review 列還寫著 `file_kind`，已改。未處理的兩條（都不是這張票造成的）：
  - `adapters/budget.SiteUsage` 的 `limit`、`window` 沒有讀者（`window_seconds` 讀的是 `BudgetView.window`，已刪）。
  - `deletion.estimate_deletion` 拿掉兩個位元組數之後，`_measure(placed)`、`_measure(paths.sources)` 只剩 `.found` 有人讀，每個檔案仍 `stat` 兩次。
