# 114 — 搜尋：HTTP 逾時不算「整台連不上」

**Status:** done

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

- [x] 所有查詢都拋 `ServiceTimeoutError` 時 `problem is None`，而且每條逐查詢列都是失敗（pytest，做變異驗證：拿掉第 2 點的分支會紅）
- [x] `httpx.ReadTimeout` 經 adapter 變成 `ServiceTimeoutError`，而且仍是 `ServiceUnavailableError`（pytest）
- [x] 所有查詢都是連線失敗（非逾時）時照舊回 `unreachable`（既有測試維持綠）
- [x] 全部檢查、pytest、vitest 綠；CHANGELOG、progress.md 已更新

## Comments

code-review（2026-10-20）未處理的發現：

- Standards（判斷題，不改）：依例外型別分類散在 `steps.failure_of`、`search._problem` 與 `_attempt` 的
  `isinstance(exc, ServiceTimeoutError)` 三處（Repeated Switches）。`_attempt` 另開一個 `except ServiceTimeoutError`
  要重複組那條失敗纜繩，收成 helper 只有一個呼叫端，維持現狀。
- Standards（判斷題，不改）：補上「或這一次答不出來」之後，走到整頁「連不上」的只剩拒絕連線、主機不在與 5xx / 429；
  後半句對 5xx / 429 成立，文案是票面第 3 點要求的。5xx / 429 的分類照票面不在本票範圍。
- Spec（記一筆）：`adapters/torrent.py` 自己把 httpx 例外對應成 `ServiceUnavailableError`、不經 `HttpSession`，
  `.torrent` 下載的逾時不會是 `ServiceTimeoutError`；沒有呼叫端需要分，不改。
- 已修：`_attempt` docstring 第三格的語意寫清楚、拿掉沒有閘門守著的「`SEARCH_TIMEOUT_SECONDS` 比 `timeout`
  短」；`ServiceTimeoutError` docstring 不再點名 services 層的消費者；`test_one_failing_query_does_not_sink_the_others`
  的假錯誤改成真實會出現的 `ServiceTimeoutError`。
