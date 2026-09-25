# 20 — 輪詢預算 + 缺集分批

**Status:** done

**Blocked by:** 12（每日補漏是預算的第三個使用者）

**讀:** plan §3.2（`rss_poller`）、§8.4（`MAX_QUERIES`、缺集一鍵搜的查詢）、§11.4（「M1.5 帶過來的一條」）；brief §15；`.scratch/m1.5/issues/10-search-missing-episodes.md`

## 做什麼

M1.5 票 10 帶過來的一條：缺集散在六季以上時，只退回作品名，不分批問。一次搜尋的查詢數上限，是為了不把公開站打到封 IP（§8.4）。**分批的節奏與 RSS 輪詢的預算是同一個決定**（plan §11.4），在這裡一起定。

- **一個站一份請求預算**：`rss_poller`、每日補漏（票 12）、缺集搜尋共用。預算的形狀先看成熟產品怎麼做（Sonarr / Prowlarr 的 indexer 查詢與抓取限制、AutoBangumi 的輪詢間隔），說明採用誰的慣例再動手，結論寫進 plan §3.2 與 §8.4。
- **缺集分批**：記號放不下 `MAX_QUERIES` 時不再退回作品名，而是照預算分批問完；畫面說得出「這一批問了哪幾季，下一批何時問」。
- 預算用完時，被延後的工作要說得出來（健康頁或 `/rss`），而不是靜默不跑。

## 驗收

- [x] 三個使用者在同一站上共用預算：造一個預算很小的設定，三者加起來不超過（整合測試）
- [x] 缺集散在七季的作品：分批問完每一季，沒有退回作品名（整合測試，Fake 索引站記下每一個查詢）
- [x] 預算用完時畫面看得到被延後的工作
- [x] plan §3.2、§8.4 同步，寫明採用了誰的慣例
- [x] lint、type、test 綠燈

## Comments

2026-09-26 實作（`adapters/budget.py`、`services/search.missing_batches`、`GET /health/budget`、`BudgetCard`）。
形狀照 Prowlarr 的 Query Limit（滾動一小時、用完拒絕不排隊、重試時刻＝最早那一筆 + 窗長），每站每小時 60 個，
記在記憶體；理由與沒做的事在 plan §3.2，研究 `docs/research/request-budget.md`，事實摘進 brief §20.13。

code-review（兩軸，基準 dc40924）已修：

- **Spec，High**：批次原本以序號定位，而批次照「現在」的缺集重切——問完第一批、從結果送了幾季之後，
  「問下一批」會落到別的季或漏掉一季。改成以季定位（`from_season=<next_seasons[0]>`），補了回歸測試
  （`test_the_next_batch_still_asks_its_seasons_after_some_were_sent`）。
- 健康頁的「延後」過了放得下的時刻仍一直列著（搜尋與人按的讀取沒有東西自己重試）：過時的不再列。
- 自動綁定被擋時同一輪又重認一次、`refused` 灌高：這一輪長出來的不重認。
- 被擋下的那一批畫面說不出是哪幾季：多一行「這一批要問 …，一個都還沒問」。
- Standards：三處相同的「預算 vs 讀不到」例外轉換收成 `rss.unread`；`_backfill` 不再把關掉的 fetcher 交給
  `_record`；兩處過時的註解；`feed_fetcher` 的約定補了閘門 `tests/unit/test_feed_fetcher_gate.py`（雙向變異）。

未處理（判斷題，留給之後決定）：

- **「照預算分批問完」解讀成下一批由人按**，不是背景自動問完：結果要人挑，背景問完沒有人看；畫面先說
  下一批何時放得下。若要自動續問，得先有「一次搜尋的結果跨批累積」的形狀。
- **Torznab 端點不和 RSS 共用預算**：Berth 看不到 Jackett / 單站 Torznab 背後是哪一站，只記在端點主機上
  （plan §8.4）。驗收第一條在 Prowlarr（預設）成立。
- **`.torrent` 下載不在預算裡**：Prowlarr 把它算在另一份 Grab Limit；Berth 目前不限（plan §3.2）。
- **沒做每秒節流與 429 逐級退避**（研究檔的第 3、5 點）：plan §3.2 記了理由。
- 範圍外但做了：作品名搜尋與 `/rss` 上人按的讀取（一次性連結、Mikan 代搜、訂閱）也吃同一份預算
  （它們打的是同一批站），後者被擋是 429 `budget_exhausted`。
- `services/health.read_budget` 只是轉手（Middle Man）：為了守 api → services 的分層留著。
- `RequestBudget` 放在 `adapters/`（與 TMDB 的 `TokenBucket` 同處）：它是對外請求的記帳，indexer adapter
  要用 `site_of`；若日後預算要讀設定或寫資料庫再搬。
- 三者共用的整合測試用的是綁定時的補舊集；每日補漏被擋在另一條測試（`test_a_backfill_that_does_not_fit_...`）。
