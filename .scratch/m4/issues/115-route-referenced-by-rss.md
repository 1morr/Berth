# 115 — Route 被 RSS 綁著時：放行要擋、刪除要拒

**Status:** done

**Blocked by:** None — can start immediately

**讀:** 票 111；`berth/services/rss.py` 的 `_release_block`、`_submit`；`berth/api/rss.py` 的 `post_item_release` 與 `_STATUS`；`berth/services/routes.py` 的 `_usages`、`_usage_of`、`delete_route`、`RouteUsage`；`berth/models/rss.py`（`route_id` 的 `ondelete="SET NULL"`，約 :71-74、:103）；`web/src/routes/`（刪除被拒時的畫面）；docs/development.md〈拒絕的理由〉

## 為什麼

協調者審查（2026-10-20）發現兩件相連的事：

1. 票 111 的 `_release_block` 只檢查 Series 有沒有綁作品，沒檢查 `route_id`。Route 被清掉的 Series，「仍然下載」照樣可按，每按一次都失敗，畫面顯示機器字串「送不出：route_missing: the series has no route」。
2. 根因：`delete_route` 的 `_usage_of` 只算 Job 與帳本，不算綁著這條 Route 的 RSS Feed / Series。一條只有被排除合集、從沒送過單的 Feed，它的 Route 刪得掉；外鍵 `SET NULL` 讓 Feed / Series 無聲失去 Route。`delete_route` 的既有規則是「被引用就拒絕，出路是停用」（票 14），RSS 的綁定也是引用，該照同一條規則。

## 做什麼

1. `_release_block`：Series 綁定檢查之後加 `series.route_id is None` → `RssRejectedError(RssRefusal.ROUTE_MISSING, …)`。`ROUTE_MISSING` 已在 enum、`_STATUS`、`REASONS`、i18n 裡，不新增理由；`post_item_release` 的 `responses=` 補上它（`TestDeclaringWhatEachEndpointRefuses` 會要求）。清單的 `release_blocked` 因為共用同一支檢查，自動說出原因。
2. `RouteUsage` 多算綁著這條 Route 的 RSS Feed 與 RSS Series（各一個數）；`in_use` 把它們算進去；`_usages`（清單）與 `_usage_of`（刪除）同一套。被拒時畫面說出「有 N 個 RSS Feed / Series 綁著」，出路照舊是停用。改了 response model 就重跑 `pnpm -C web gen:api`。
3. 已經因為過去刪 Route 而 `route_id` 變 NULL 的 Feed / Series 不做 migration：RSS 頁本來就讓使用者重選 Route（票 105）。

## 驗收

- [x] Route 被清掉的 Series：清單的 `release_blocked` 是 `route_missing`、放行回 422 `route_missing`、Item 不變（pytest，做變異驗證）
- [x] 有 RSS Feed 或 Series 綁著的 Route 刪除被拒（`route_in_use`），計數正確；沒人綁的照舊刪得掉（pytest）
- [x] Route 頁的刪除被拒畫面說出 RSS 綁定的數量（vitest，zh-Hant 與 en）
- [x] 全部檢查、pytest、vitest 綠；plan（Route 刪除規則）、CHANGELOG、progress.md 已更新

## Comments

- code-review（2026-10-20）未處理的發現：
  - `Media.default_route_id` 也是 `ondelete="SET NULL"`，刪 Route 時無聲清掉，`RouteUsage` 沒算它。票面沒要求，留給之後的票決定要不要算成引用。
  - 四個引用數（`jobs`、`ledger_entries`、`rss_feeds`、`rss_series`）在 `ManagedRouteOut`、`RouteRefusalOut`、`route_refusal`、前端 `usageOf` 逐欄重寫（Data Clumps）。收成一個巢狀 `usage` 物件會改對外 API 形狀，沒做。
