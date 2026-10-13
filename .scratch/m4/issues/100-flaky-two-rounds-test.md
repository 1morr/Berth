# 100 — 修穩 `TestTwoRoundsAtOnce::test_only_one_round_runs_and_neither_fails`

**Status:** ready-for-agent

**Blocked by:** None — can start immediately

**讀:** `tests/integration/test_rss.py` 的 `TestTwoRoundsAtOnce`（同一個 class 裡第二條用 `_GatedFetcher` 的寫法）；M4 票 13c（這組測試的由來）；票 49 的 Comments（第一次記到失敗）；`berth/services/rss.py` 的 `poll_feed`、`poll_due` 與 Feed 鎖

## 為什麼

這條測試在全套 pytest 時偶爾紅，單獨跑都綠。2026-10-07（票 49）記過一次，2026-10-13 合併票 94、98 時又各紅一次。每次都得重跑，久了大家會習慣「紅了就重跑」，哪天真的錯誤就混過去了。使用者（2026-10-14）同意開票修。

票 49 記下的失敗是 `(12, 0) != (12, 1)`：背景那一輪晚到，Feed 已經被「立即輪詢」輪過、不再到期，`poll_due` 就輪 0 個。

初步看法（**未證實**，開工時先證實）：
- 這條用 `asyncio.gather` 同時起兩邊，但沒有任何東西保證兩邊真的重疊。
- 「立即輪詢」整輪跑完之後背景那一輪才進來，是合法的排程。這時產品行為是對的（Feed 不再到期），是測試的斷言假設了重疊。
- 同一個 class 的第二條用 `_GatedFetcher` 把 Feed 卡住，確保重疊，所以穩定。

## 做什麼

1. **先重現**：用固定的排程（例如讓背景那一輪晚一點進來）穩定重現 `(12, 0)`，確認上面的看法。如果根因不是這個，停下來在票的 Comments 寫清楚實際原因，不要硬修。
2. **確認是測試的問題之後**：用 `_GatedFetcher`（或同等的閘）讓兩邊確實重疊，斷言的意思不變——人先到、背景後到時，只輪一輪、兩邊都不報錯。
3. 如果查出來是產品的競態（例如鎖沒有涵蓋到某一段），就修產品並補一條會穩定紅的測試。
4. 不要用重試、放寬斷言或 `flaky` 標記掩蓋。

## 驗收

- [ ] 根因寫在票的 Comments，附重現方法
- [ ] 修好之後，這條測試連跑 50 次（例如 `pytest --count` 或迴圈）全綠，貼輸出；全套 pytest 連跑 3 次都綠
- [ ] 改測試的話，變異驗證：把閘拿掉，能穩定重現原本的失敗
- [ ] 全部檢查、pytest 綠；progress.md 已更新
