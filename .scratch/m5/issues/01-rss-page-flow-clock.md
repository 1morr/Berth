# 01 — RSS 頁流程測試固定時間

**Status:** done

**Blocked by:** None — can start immediately

**讀:** plan §11.5〈M5 開工前的審查補記〉「排進 M5 開頭」；`parser.series_finished` 與 `QUIET_AFTER` 的 docstring；參考 `backup/m5-attempt-1-20261024` 的 `952dc73`

## 為什麼

`tests/integration/test_rss_api.py::TestThePageFlow::test_add_poll_bind_and_see_the_jobs` 照讀清單那一刻的牆上時間算「已完結」（設計如此）。錄下來的 feed 最新一集在 2026-10-24 超過 `QUIET_AFTER`，斷言從 `False` 變成 `True`，`main` 從那天起每天紅（2026-10-24 審查實跑：`(2, 12, True) != (2, 12, False)`）。後面每張票的 CI 都會被它拖紅，最先修。

## 做什麼

1. 先跑一次看它紅（repro）。
2. 用 time-machine 把那條測試的「今天」固定在錄下的最新一集的隔天，並加一段斷言：時間跳過 `QUIET_AFTER` 之後「已完結」翻成 `True`——行為本身有被守，不只是把時間凍住。
3. 掃一遍其他整合測試有沒有同一種照牆上時間算、依賴錄下日期的斷言（`QUIET_AFTER`、`series_finished`、「幾天前」這類）；有的話一起固定，沒有就在票上寫掃過什麼。

## 驗收

- [x] 改之前紅、改之後綠（貼兩次輸出）
- [x] 時間跳過 `QUIET_AFTER` 時「已完結」翻轉的斷言存在
- [x] 其他依賴錄下日期的測試掃過，結果寫在票上
- [x] 全部檢查、pytest 綠；progress.md 已更新

## Comments

### 原因與修法（2026-10-25）

測試的問題，產品沒錯：`GET /api/rss/series` → `services.rss.list_series` 取 `now or utcnow()` → `parser.series_finished`，「已完結」照讀清單那一刻的牆上時間算（docstring 寫明是設計）。錄下的《与你相恋》最新一筆是 2026-09-24 08:08 UTC，加 `QUIET_AFTER`（30 天）就是 2026-10-24。

移植第一次嘗試的 `952dc73`：`TestThePageFlow::test_add_poll_bind_and_see_the_jobs` 開頭用 time-machine 的 `time_machine` fixture 固定在 `KIMI_NEXT_DAY`（從錄下的 feed 算出的最新一筆隔天），結尾跳到 `KIMI_NEXT_DAY + QUIET_AFTER`、重新登入（session 也照同一個時鐘過期），斷言同一列 `finished is True`。新 dev 依賴 `time-machine>=3.5.1`（`uv add --dev`，lock 由 uv 重產）；`docs/development.md`〈後端〉補「測試裡的『現在』」一段。

### 改之前紅、改之後綠

```
# 改之前
E       assert (2, 12, True) == (2, 12, False)
FAILED tests/integration/test_rss_api.py::TestThePageFlow::test_add_poll_bind_and_see_the_jobs
1 failed, 29 passed in 20.64s
# 改之後
30 passed in 19.61s
```

變異：把跳過 `QUIET_AFTER` 那一行換成 `pass`，最後一條斷言紅（`assert False is True`）。

### 掃描其他依賴錄下日期的測試

- 讀程式碼：`tests/integration` 裡 `QUIET_AFTER`、`series_finished`、`finished` 的斷言（`test_rss_series_view.py`、`test_rss_backfill.py`）都傳顯式的 `now=` 對 fixture 日期；`utcnow()` / `datetime.now(UTC)` 的其他用法（`test_plan`、`test_search`、`test_media`、`test_discover`、`test_submit_guards`、`test_inventory`、`test_sweep_gaps` 等）都是「現在 ± 相對量」對「現在」，不會隨日期翻面。
- 實跑：暫時的 pytest plugin（沒進 repo）在 session 開頭 `time_machine.travel(timedelta(days=N), tick=True)`，跑整個 `tests/integration`：

```
N=400:  2608 passed
N=3650: 2608 passed
N=-60:  1 failed, 2607 passed   # test_reimport，見下
```

- 往回推 60 天紅的 `test_reimport.py::TestRebuildingADeletedLibrary::test_jellyfin_finds_every_episode_again`：入庫用寫死的 `arrange.NOW`（2026-09-08），反查掃描用 `utcnow()`，只在時鐘早於那天時紅，往後永遠綠，**不是定時炸彈，不修**（與第一次嘗試的結論相同）。
- 掃描的極限：抓得到「過了某一天就翻面」的，抓不到只在某段時間窗才紅的（跨年、月底）。

### code-review（基準 `913e64cc`）

已改：註解裡「一個月後重新登入」把 `QUIET_AFTER` 的值寫進文字，改成「跳過去之後」。未處理（判斷題）：同一條測試兩份 `next(row for row in client.get("/api/rss/series").json() if row["key"] == KIMI_KEY)`，只有兩處不抽；`KIMI_NEXT_DAY` 說的是怎麼算而非用途（審查建議 `PAGE_FLOW_TODAY`），有 `#:` 註解，保留；翻面斷言放在同一個測試結尾，前面紅了它就不跑，票只要求斷言存在，保留。Spec 軸沒有缺漏或範圍外的改動。
