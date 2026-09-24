# 02 — 卡死的 Job 與管線 Issue 自收

**Status:** ready-for-agent

**Blocked by:** None — can start immediately

**讀:** plan §11.4「M3 之前先做的修補」、§3.1（`requested` / `submit_failed` 與 Issue 動作那幾列）、§3.2（`qbit_poller`、迴圈的例外處理）、§2.4（`issues` 的系統自收）；`.scratch/m2/issues/09c-pipeline-issue-actions.md` 的 Comments（延後項與它的失效條件）

## 做什麼

RSS 半夜送出去的單沒有人看著，下面三種 Job 會一直停在原地，而畫面說不出為什麼。

- **`submit_failed` 但 qBittorrent 其實收下了**（逾時、回應讀到一半斷線）：poller 在客戶端看到同一個 hash 時要把它認回來，推到 `submitted` 以後照常走，不要當成 `unknown_torrent`。
- **`requested` 在程序中途掛掉**：重啟後要有出路。照 §3.1 已有的形狀選一條（重送，或落到 `submit_failed` 讓重試接手），並把理由寫進 plan。
- **`guarded` 吞掉的非預期例外**：寫進 `Job.error` 與時間線。現在只進 log，畫面上的 Job 看起來是好的。

**管線 Issue 由系統收**（M2 票 09c 的延後項，失效條件在那張票上）：`missing_files` / `client_error` / `client_removed` 在 Job 被別處修好之後（使用者在 qBittorrent 裡自己 recheck、重新加回 torrent），由系統以 `resolved_by = system` 收掉。做法照 §2.4 其他幾種自收的先例。

## 驗收

- [ ] `submit_failed` 的 Job 在 qBittorrent 裡有同一個 hash → poller 一輪之後是 `submitted`（或更後面），沒有開 `unknown_torrent`（整合測試，Fake qBittorrent）
- [ ] 停在 `requested` 的 Job 重啟後不會永遠停在那裡（整合測試），plan §3.1 寫明走哪一條
- [ ] 迴圈裡的非預期例外讓那一筆 Job 的 `error` 與時間線有一筆說明；迴圈本身不死（整合測試）
- [ ] 三種管線 Issue：Job 回到正常狀態之後由系統收掉，`resolved_by = system`；Job 還壞著的時候不收（每一種一條雙向測試）
- [ ] lint、type、test 綠燈
