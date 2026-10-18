# 107 — 刪除站點請求預算

**Status:** ready-for-agent

**Blocked by:** None — can start immediately

**讀:** plan §3.2（`rss_poller` 那一段的「一個站一份請求預算」）、§8.4；brief §20.7、§20.13（三站沒有公開的限速紀錄）；`berth/adapters/budget.py`；progress.md 2026-10-09 票 77 那幾行

## 為什麼

使用者 2026-10-19 拍板全刪。

- 每站每小時 60 個的上限不是量出來的：brief §20 記載 Mikan、Nyaa、acg.rip 都找不到公開的限速或封鎖紀錄，60 是照用量推的（plan §3.2）。
- 實際擋到人的只有 Berth 自己：票 77 的紀錄是「使用者訂閱 MyBangumi 後 Mikan 一小時的額度被 RSS 用完」，被擋的是 Berth 自己的計數，不是站點。
- 搜尋經過 Prowlarr，而 Prowlarr 每個索引站本來就有可設定的 Query Limit。Berth 再管一層等於雙重限制，使用者看不到也調不了。
- 站點真的回 429 / 5xx 時，現有退路照樣接得住：Feed 與單集頁「讀不到、記 `last_error`、下一輪再試」，自動綁定的 `lookup_retry`（票 14）。

## 做什麼

1. **刪掉** `berth/adapters/budget.py`（`RequestBudget`、`BudgetedFetcher`、`BudgetExhaustedError`、`site_of` 若沒有別的消費點）、`BudgetUse`、`ServiceClientFactory.budget`，以及各處的 `take` / `take_each` / `ready_at` 呼叫。
2. **RSS**：`RssRefusal.BUDGET_EXHAUSTED` 與它的 429 刪掉。自動綁定的 `lookup_deferred` 理由刪掉，只剩 `lookup_retry` / `lookup_failed`。
3. **搜尋**：`budget_exhausted`、結果的 `skipped`、`retry_at` / `next_at`、只帶部分 `indexerIds` 的路徑刪掉，照舊整批問全部。`IndexerSearch.sites()` 如果只剩預算在用，連同測試一起刪（全域規則：消費點歸零的介面連同守它的測試一起刪）。
4. **健康頁**：`GET /health/budget`、`BudgetCard`、相關 i18n（zh-Hant、en）刪掉。
5. **資料 migration**：`rss_series.reasons_json` 裡還帶 `lookup_deferred` 的 Series，改成下一輪就到期的 `lookup_retry`，而且不算一次失敗。不處理的話它們永遠不會再被重認，會一直卡在待綁定。`lookup_retry` 的結構裝不下「不算一次失敗」的話，停下回報，不要自行拍板。
6. **閘門**：`tests/unit/test_feed_fetcher_gate.py`、`test_request_budget.py` 如果守的是「每個請求都經過預算」，就連同預算一起刪。commit body 要交代撤掉的閘門由誰接手；沒有接手的，照實寫「回到沒有閘門」。
7. **不動** `berth/adapters/rate.py`：那是 TMDB 的每秒令牌桶，和站點預算是兩回事。
8. **文件**：plan §3.2、§8.4 與 brief 裡請求預算的段落改寫，或註明已推翻；CONTEXT.md 刪「請求預算」條目；CHANGELOG `[Unreleased]` 的 Removed 寫明 `GET /health/budget` 與搜尋回應欄位的移除（對外 API 的破壞性變更，前端是唯一消費者）；progress.md「偏差與決定」記一行，推翻 M3 票 20 與 M4 票 77。

## 不做

- 每秒節流、站點層級的逐級退避：研究檔當初就沒做，現在也沒有 repro。

## 驗收

- [ ] `rg -i "budget|BudgetUse|lookup_deferred|budget_exhausted" berth web/src tests` 只剩 AI 月預算那類無關的命中（貼輸出）
- [ ] 帶 `lookup_deferred` 的 Series 經 migration 後，下一輪輪詢會重認（pytest；alembic upgrade / downgrade 都跑過）
- [ ] 搜尋不再跳過任何站，也不再回 `budget_exhausted`（pytest、vitest）
- [ ] 健康頁不再出現請求預算卡（vitest；playwright 實跑截圖）
- [ ] 全部檢查、pytest、vitest 綠；plan、brief、CONTEXT.md、CHANGELOG、progress.md 已更新

## Comments
