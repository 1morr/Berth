# 02 — 卡死的 Job 與管線 Issue 自收

**Status:** done

**Blocked by:** None — can start immediately

**讀:** plan §11.4「M3 之前先做的修補」、§3.1（`requested` / `submit_failed` 與 Issue 動作那幾列）、§3.2（`qbit_poller`、迴圈的例外處理）、§2.4（`issues` 的系統自收）；`.scratch/m2/issues/09c-pipeline-issue-actions.md` 的 Comments（延後項與它的失效條件）

## 做什麼

RSS 半夜送出去的單沒有人看著，下面三種 Job 會一直停在原地，而畫面說不出為什麼。

- **`submit_failed` 但 qBittorrent 其實收下了**（逾時、回應讀到一半斷線）：poller 在客戶端看到同一個 hash 時要把它認回來，推到 `submitted` 以後照常走，不要當成 `unknown_torrent`。
- **`requested` 在程序中途掛掉**：重啟後要有出路。照 §3.1 已有的形狀選一條（重送，或落到 `submit_failed` 讓重試接手），並把理由寫進 plan。
- **`guarded` 吞掉的非預期例外**：寫進 `Job.error` 與時間線。現在只進 log，畫面上的 Job 看起來是好的。

**管線 Issue 由系統收**（M2 票 09c 的延後項，失效條件在那張票上）：`missing_files` / `client_error` / `client_removed` 在 Job 被別處修好之後（使用者在 qBittorrent 裡自己 recheck、重新加回 torrent），由系統以 `resolved_by = system` 收掉。做法照 §2.4 其他幾種自收的先例。

## 驗收

- [x] `submit_failed` 的 Job 在 qBittorrent 裡有同一個 hash → poller 一輪之後是 `submitted`（或更後面），沒有開 `unknown_torrent`（整合測試，Fake qBittorrent）
- [x] 停在 `requested` 的 Job 重啟後不會永遠停在那裡（整合測試），plan §3.1 寫明走哪一條
- [x] 迴圈裡的非預期例外讓那一筆 Job 的 `error` 與時間線有一筆說明；迴圈本身不死（整合測試）
- [x] 三種管線 Issue：Job 回到正常狀態之後由系統收掉，`resolved_by = system`；Job 還壞著的時候不收（每一種一條雙向測試）
- [x] lint、type、test 綠燈

## Comments

- 2026-09-24 實作：`requested` 走「啟動時落到 `submit_failed`」（理由在 plan §3.1 那一列）；poller 除了
  `submit_failed` 也接回 `missing_files` / `client_error` / `client_removed`（不接回的話 Job 停在壞掉狀態，
  Issue 就永遠收不掉）；Job 被刪掉的管線 Issue 也由系統收（比票面寬，理由在 progress.md 偏差）。
  新事件 `recovered`、`round_failed`，前端時間線逐種一句話。
- 2026-09-24 playwright 對 `--scenario issues` 實跑：三件管線 Issue 開著 → 新的演練端點
  `POST /demo/qbittorrent/fix?hash=` 在替身 qBittorrent 裡修好三筆 → poller 下一輪三筆都是 `downloading`、
  三件 `resolved_by = system`、`/issues` 只剩無主 torrent；詳情頁時間線「已接回 · qBittorrent 裡的檔案回來了，
  接著下載。 · downloading」。`round_failed` 以手寫一列事件驗渲染（錯誤原文紅字），爆掉本身由整合測試驗。
- 2026-09-24 變異：接回查詢、不接回的前提、檔案在不在、凍結、自收（不收 / 全收）、啟動落地、記錄錯誤、
  同一錯誤不重寫、事件去重界線，十條逐一拿掉都有測試轉紅；importer 那一側的記錄另一條。
- 2026-09-24 code-review 未處理的發現：
  - Spec：壞掉狀態之間不互通——`client_error` 的 Job 若客戶端改報 `missingFiles`，poller 不接回也不轉，
    它停在 `client_error`（`client_state` 也不更新），Issue 給的是「重試」而不是「重新校驗」。不是退步
    （之前 poller 根本不看這幾個狀態），要轉的話是 plan §3.1 的一條新轉換，等有 repro 再決定。
  - Spec：`submit_failed` 接回時 Route 已被刪就不凍結資料夾名（送單成功那條路一定有 Route）。邊界，沒處理。
  - Standards（判斷題）：「system」actor 有兩種寫法（`downloads.SYSTEM` 與 `actor_of(None)`），
    `SYSTEM = "system"` 本來就定義在三個模組；沒有在這一票收斂。
