# 129 — 每日巡檢：卡住的與放太久的

**Status:** done

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

- [x] 巡檢一天只跑一輪、重啟不立刻跑（pytest，假時鐘）
- [x] 卡住超過門檻的 RSS Series 第一批開一件 Issue，條件消失後由系統收掉（pytest）
- [x] 已有 Issue 管的卡死狀態不重複開（pytest）
- [x] 最舊一件超過 3 天 → 提醒一則；三天內不重複（pytest）
- [x] 新 Issue 類型在 `/issues` 有人話（vitest）
- [x] 巡檢耗時記在 Comments
- [x] 全部檢查、pytest、vitest 綠；plan §3.2 補巡檢迴圈；CONTEXT.md「巡檢」；CHANGELOG、progress.md 已更新

## Comments

- **命名**：CONTEXT.md 的「巡檢」是 **Sweep**，所以迴圈是 `sweeper`（`pipeline/sweeping.py`），一輪是
  `services.sweep.sweep_once`，自己的紀錄是 `settings.sweep`。每日 05:00（容器的 `TZ`），與 04:00 的對帳錯開。
- **卡住的 Job 盤點**（第 2 點）：`client_error` / `missing_files` / `client_removed` 各有管線 Issue
  （`client_removed` 重新送單被拒、落回 `submit_failed` 的那一筆也算在它下面）；`review` 在審核佇列。
  `submit_failed`（暫時性失敗由 `jobs.retry_due` 重送，用完或永久失敗之後）、`import_failed`、`stalled` 沒有 Issue，
  只在下載頁「需要人」的篩選與 Job 頁上。這張只補票面點名的那一條（`first_batch_stuck`），其餘三種要不要進
  「等你處理」留給 133 驗收或之後有 repro 時決定。
- **量測**（第 5 點，`scripts/experiments/sweep_loop_lag.py`，2026-10-22，本機 Windows、暫時的 SQLite）：
  400 個 RSS Series × 12 筆 Job × 8 筆事件、300 件開著的 Issue，一輪 226–343 ms，事件迴圈最久被佔
  **5–27 ms**（另一個 coroutine 每 1 ms 醒一次量到的最大延遲，三輪）；放大五倍（2,000 個 Series、1,000 件卡住、
  1,000 件 Issue）一輪 1.1–1.8 s，最久 **15–37 ms**。都在 100 ms 以下，不另開票、不移出事件迴圈。
- 實跑：`fake_setup_server.py --scenario issues` 上造一個停在送單失敗 30 小時的 RSS Series、跑 `sweep_once`，
  `/issues` 出現「第一批卡住」，展開看得到停在、停住於、原因、下一步與那一筆下載的連結
  （`.playwright-mcp/t129-first-batch-stuck.png`）；實跑抓到「下一步」說「下面那一筆」而下載那一格在上面，已改。
- **code-review**（兩軸，起點 `8c006cec`）處理掉的：development.md 的票路徑被改名誤傷（Standards）；`IssueSubject.RSS_SERIES`
  的註解說畫面靠它連到 RSS 頁，前端沒有（Standards、Spec，改註解）；實驗 README 的例外理由沒涵蓋巡檢（Standards）；
  被忽略的管線 Issue 也算「已有 Issue 管」（Spec，判斷題，progress 偏差）；一輪的門檻照排定的 05:00 算、不照醒來那一秒，
  否則「3 天」有時是 4 天（Spec）；沒有人收得到時不記提醒過（Spec）。三條行為修正都先紅後綠。
- **code-review 沒處理的**：
  - `Sweeper` 與 `Reconciler` 的排程幾乎逐行相同（Standards，Duplicated Code）：只有兩份，第三個每日迴圈出現再抽。
  - `_render_lingering` 的「每一種幾件」欄位與 `_render_waiting` 重複、`_waiting_recipients` 是從 `_queue_waiting`
    抽出來的（Standards、Spec）：協調說 notify.py 盡量不搬，所以重複留著；抽收件人那一處是規則不能分岔（progress 偏差）。
  - 前端 `STUCK_STATES` 抄了後端 `sweep._STUCK_STATES`，沒有閘門（Standards）：後端多一種時前端只是少畫「停在」那一行。
  - `subject_of` / `record_issue` 每多一種 `IssueSubject` 多一個平行參數（Standards，Data Clumps）；`sweep` 在
    `record_issue` 之後自己改 `job_hash`（Feature Envy）：`record_issue` 對既有列只更新 detail 與時間，這是唯一一個
    要換弱引用的生產者，沒改它的語意。
  - 列上的下一步提到審核頁，但沒有連結（Spec）：審核頁那一組沒有以 Series 為單位的錨點；下載那一格連得到停住的那一筆。
