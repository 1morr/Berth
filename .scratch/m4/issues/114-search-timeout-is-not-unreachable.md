# 114 — 搜尋：HTTP 逾時不算「整台連不上」

**Status:** ready-for-agent

**Blocked by:** None — can start immediately

**讀:** 票 107 的「偏差與決定」（progress.md）；`berth/services/search.py`（`_attempt`、判 `problem` 的那段，約 :400-540）；`berth/adapters/http.py`（例外對應，約 :150-170）；`berth/adapters/indexer/prowlarr.py` 的 `SEARCH_TIMEOUT_SECONDS`；`berth/services/steps.py` 的 `failure_of`；`tests/integration/test_search.py`

## 為什麼

票 107 拿掉搜尋前的 `sites()` 預檢，改成「每一個查詢都以 `ServiceError` 失敗」才回 `unreachable` / `credential_rejected`，並寫明「逾時不算」。但只排除了 service 層 `asyncio.timeout`（150 秒）拋的 `TimeoutError`；HTTP 層的逾時（`SEARCH_TIMEOUT_SECONDS = 120`，一定先到）被 `http.py` 包成 `ServiceUnavailableError("...: ReadTimeout")`，照樣算進「整台壞」。

失效情境：只打一個關鍵字，或 Prowlarr 冷啟動慢（brief 實測 60–85 秒，多查詢並發時更久），每個查詢都超過 120 秒 → 全部 ReadTimeout → 整頁顯示「連不上索引站」，逐查詢的失敗列不見。票 107 之前這個情況只會是紅色的逐查詢列。這是退化。

協調者審查（2026-10-20）確認：5xx / 429 被歸成「連不上」與票 107 之前同一分類（舊的 `failure_of` 就這樣對），不在本票範圍。

## 做什麼

1. `berth/adapters/http.py`：在 `ConnectTimeout` 分支之後，`httpx.TimeoutException` 改拋新的子類 `ServiceTimeoutError(ServiceUnavailableError)`。是子類，所以 `failure_of`、`is_transient` 與其他 `isinstance` 判斷照舊。
2. `search.py` 的 `_attempt`：`ServiceTimeoutError` 與 `TimeoutError` 同等處理——逐查詢列照樣用 `failure_of(exc)` 顯示失敗，但不算進「整台壞」。修正那段註解。
3. `search.problem.unreachable.body`（zh-Hant 與 en）補上逐查詢列已有的「或這一次答不出來」那層意思。

## 驗收

- [ ] 所有查詢都拋 `ServiceTimeoutError` 時 `problem is None`，而且每條逐查詢列都是失敗（pytest，做變異驗證：拿掉第 2 點的分支會紅）
- [ ] `httpx.ReadTimeout` 經 adapter 變成 `ServiceTimeoutError`，而且仍是 `ServiceUnavailableError`（pytest）
- [ ] 所有查詢都是連線失敗（非逾時）時照舊回 `unreachable`（既有測試維持綠）
- [ ] 全部檢查、pytest、vitest 綠；CHANGELOG、progress.md 已更新
