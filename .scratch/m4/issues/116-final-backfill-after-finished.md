# 116 — 完結之後再補最後一次漏

**Status:** ready-for-agent

**Blocked by:** None — can start immediately

**讀:** 票 108；`berth/services/rss.py` 的 `_backfill_due`（約 :1190-1200）、`_finished`、`_finished_now`；`berth/parser/finished.py`；`tests/integration/test_rss_backfill.py::TestFinishedStopsBackfill`；plan §3.2（約 :211、:218）；brief §15（約 :574）、§20 聚合 feed 的實測（約 :1541）；CONTEXT.md〈補舊集〉

## 為什麼

票 108 讓完結的 RSS Series 停止每日補漏。協調者審查（2026-10-20）找到一條無聲漏集的路：

- 聚合 feed 只有約 12 筆、6.6 天（brief 實測）。Berth 停機約 4–5 週，期間剛好播完最後幾集；重啟時最近一筆已超過 `QUIET_AFTER`（30 天，從**最近一筆的發佈時間**算）。
- 聚合 feed 裡已沒有這部的新一筆 → 判為完結 → `_backfill_due` 跳過 → 最後幾集永遠補不回來，畫面只說「已完結，不再補漏」。
- 這正是每日補漏存在的理由。票 108 之前這個情況補得回來。字幕組晚發（實測最長隔 22 天）時，需要的停機更短。

另外 plan :218「停機少於 `QUIET_AFTER`（30 天）時，重啟之後還沒完結」不準：30 天是從最近一筆算，不是從停機算。

## 做什麼

1. `_backfill_due`：只有「現在已完結」**而且**「上次補漏那一刻也已完結」才跳過（`backfilled_at` 為 None 時照讀）。兩個判斷都用同一支 `_finished_now`，不另寫規則。代價是每部作品完結後多讀一次單一 feed。
2. 文件：plan §3.2 改成「完結後再補最後一次就停；停機跨過 `QUIET_AFTER` 時被捲掉的最後幾集靠這一次接住」，拿掉「停機少於 30 天」那句；brief §15、CONTEXT.md〈補舊集〉同步；progress「偏差與決定」記一行。畫面文案「已完結，不再補漏」不改。

## 驗收

- [ ] 上次補漏時還沒完結、現在已完結的 Series：這一輪讀一次單一 feed，`backfilled_at` 更新；下一輪起不再讀（pytest，改 `test_a_finished_series_is_not_read_until_a_new_release_appears`）
- [ ] 兩個時間點都已完結的不讀（pytest，做變異驗證：拿掉第二個條件會紅）
- [ ] 全部檢查、pytest、vitest 綠；plan、brief、CONTEXT.md、CHANGELOG、progress.md 已更新
