# 01 — RSS 頁流程測試固定時間

**Status:** ready-for-agent

**Blocked by:** None — can start immediately

**讀:** plan §11.5〈M5 開工前的審查補記〉「排進 M5 開頭」；`parser.series_finished` 與 `QUIET_AFTER` 的 docstring；參考 `backup/m5-attempt-1-20261024` 的 `952dc73`

## 為什麼

`tests/integration/test_rss_api.py::TestThePageFlow::test_add_poll_bind_and_see_the_jobs` 照讀清單那一刻的牆上時間算「已完結」（設計如此）。錄下來的 feed 最新一集在 2026-10-24 超過 `QUIET_AFTER`，斷言從 `False` 變成 `True`，`main` 從那天起每天紅（2026-10-24 審查實跑：`(2, 12, True) != (2, 12, False)`）。後面每張票的 CI 都會被它拖紅，最先修。

## 做什麼

1. 先跑一次看它紅（repro）。
2. 用 time-machine 把那條測試的「今天」固定在錄下的最新一集的隔天，並加一段斷言：時間跳過 `QUIET_AFTER` 之後「已完結」翻成 `True`——行為本身有被守，不只是把時間凍住。
3. 掃一遍其他整合測試有沒有同一種照牆上時間算、依賴錄下日期的斷言（`QUIET_AFTER`、`series_finished`、「幾天前」這類）；有的話一起固定，沒有就在票上寫掃過什麼。

## 驗收

- [ ] 改之前紅、改之後綠（貼兩次輸出）
- [ ] 時間跳過 `QUIET_AFTER` 時「已完結」翻轉的斷言存在
- [ ] 其他依賴錄下日期的測試掃過，結果寫在票上
- [ ] 全部檢查、pytest 綠；progress.md 已更新
