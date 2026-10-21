# 129 — 每日巡檢：卡住的與放太久的

**Status:** ready-for-agent

**Blocked by:** 127

**讀:** plan §11.5〈巡檢〉與〈修補段結案時票 Comments 的遺留〉、§3.2（`reconciler` 每日 04:00 的排程寫法）；`berth/pipeline/reconciling.py`；`berth/domain/enums.py` 的 `IssueType`；M4 票 11 的 Comments（約 :46）、M4 票 13b 的 Comments（約 :70）；M3 票 02（卡死的 Job 已有的出路）

## 為什麼

M4 的巡檢是每天一次、不花 token 的程式檢查。這張建迴圈並做與 RSS 無關的兩類；RSS 的三類是票 130。

## 做什麼

1. 新的每日巡檢迴圈，排程照 `reconciler` 的寫法（醒得比跑頻繁、啟動不立刻跑），時間與 04:00 對帳錯開。
2. **卡住的**：先盤點現有 Issue 類型與 M3 票 02 已經涵蓋的卡死狀態，**已有 Issue 管的不重複開**；只補沒人管的，至少包括「同一個 RSS Series 有 Job 卡在 `submit_failed` / `client_error`，第一批一直等人確認」（M4 票 11 的遺留）。門檻預設 24 小時。
3. **放太久**：「等你處理」裡最舊的一件超過 3 天，給訂閱了的管理員再提醒一則（同一件三天內只提醒一次）。
4. 新的 Issue 類型照現有的 Issue 慣例（列在 `/issues`、有人話、有能做的動作；沒有動作的寫明為什麼）。
5. 量一輪巡檢佔用事件迴圈多久（M4 票 13b 的遺留），數字寫在 Comments；超過 100 ms 才另開票處理。

## 驗收

- [ ] 巡檢一天只跑一輪、重啟不立刻跑（pytest，假時鐘）
- [ ] 卡住超過門檻的 RSS Series 第一批開一件 Issue，條件消失後由系統收掉（pytest）
- [ ] 已有 Issue 管的卡死狀態不重複開（pytest）
- [ ] 最舊一件超過 3 天 → 提醒一則；三天內不重複（pytest）
- [ ] 新 Issue 類型在 `/issues` 有人話（vitest）
- [ ] 巡檢耗時記在 Comments
- [ ] 全部檢查、pytest、vitest 綠；plan §3.2 補巡檢迴圈；CONTEXT.md「巡檢」；CHANGELOG、progress.md 已更新
