# 122 — 忽略的 Issue 在條件持續期間不再重開

**Status:** done

**Blocked by:** None — can start immediately

**讀:** plan §11.5〈M3 收尾帶過來的兩條〉（含 2026-09-26 補）；M3 票 17（`.scratch/m3/issues/17-jellyfin-verify.md`）的 Comments；`berth/services/health_issues.py` 的 `_settle`、`_still_ignored`；`berth/services/resolver.py` 的 `settle_verdicts`；brief §9.1

## 為什麼

`jellyfin_item_mismatch` 被「忽略」之後，第二天對帳又把它重開。健康檢查那邊已經有「條件持續期間忽略有效、條件消失（`cleared_at`）之後再發生才重開」的規則，但 `cleared_at` 只有 `health_issues._settle` 會寫，`resolver.settle_verdicts` 不寫、也不看 `IGNORED`。不修的話，票 127 的「等你處理」會為同一件被忽略的事每天推一次。

## 做什麼

1. `settle_verdicts` 管的 Issue 類型用同一套規則：條件消失時寫 `cleared_at`；條件仍在、上一筆被忽略而且沒有 `cleared_at` 時不重開。規則只有一份——把 `_still_ignored` 與寫 `cleared_at` 的那一段搬到兩邊都用得到的地方，不複製。
2. 盤點其他會重開 Issue 的路徑（對帳的各種類型）是否有同樣的洞；有就一起修，沒有就在票的 Comments 說查過哪些。

## 驗收

- [x] 忽略一件 `jellyfin_item_mismatch`，下一輪同樣不一致：不重開（pytest）
- [x] 條件消失一輪之後再出現：重開（pytest；變異：拿掉 `cleared_at` 的寫入會紅）
- [x] 規則只有一份實作（兩條路徑呼叫同一支）
- [x] 全部檢查、pytest 綠；CHANGELOG〈Fixed〉一條；plan §11.5 那兩條標「票 122 做完」的那一條；progress.md 已更新

## Comments

2026-10-21 實作：

- **規則的位置**：判斷在 `issues.record_issue`（`STAYS_IGNORED` 裡的型別，最後一筆被忽略又沒有 `cleared_at` 就回 `Recorded(held=True)`、什麼都不寫），寫 `cleared_at` 在 `issues.note_cleared`；健康檢查（`_settle`）、回驗（`resolver.settle_verdicts`）、poller（`downloads._record_unknown`）三處呼叫同一支。判斷放進 `record_issue` 而不是各生產者，是因為 `unknown_torrent` 有兩個生產者。`health_issues._still_ignored` 刪掉，`_settle` 收開著的改用 `clear_by_system`（`health_issues.SYSTEM` 一併刪）。
- **盤點（第 2 點）**，會開 Issue 的路徑都查過：
  - `unknown_torrent`：**有同樣的洞而且更嚴重**——poller 每 5 秒寫一次，按忽略 5 秒內重開。使用者拍板一起修（`STAYS_IGNORED`）。解除由 poller 記（`sync` 是整份客戶端），對帳那一個生產者只寫不記。
  - 對帳的其餘六種（`library_link_missing`、`source_missing`、`inode_mismatch`、`orphan_complete`、`unmanaged_library_file`、`job_without_files`）：每日重開一次，但這是 brief §9.1 定的「這一次不處理」（`test_reopening_after_an_ignore_counts_as_opened` 守著）。使用者決定維持；票 127 的「等你處理」要不要為它們每天推，在 127 定。
  - 管線那四種（`missing_files`、`client_error`、`client_removed`、`jellyfin_item_unresolved`）：事件觸發（Job 轉進那個狀態才寫一次），不是週期量測，沒有這個洞。`ledger_rebuild` 的 `unmanaged_library_file` 是按一次才跑，同上。
- 測試：`test_jellyfin_verify.py::TestIgnoringIt` 三條（含 Jellyfin 問不到不算解除）、`test_downloads.py::TestIgnoringAnUnknownTorrent` 三條（含 qBittorrent 問不到不算解除）；`test_health_issues.py::TestIgnoringIt` 照舊綠，是搬家之後的回歸。變異：拿掉 `settle_verdicts` 的 `note_cleared` 時「一致一輪之後再不一致會重開」那條紅（手跑過）；poller 那條在補上 `note_cleared` 之前是紅的。

code-review（Standards / Spec 兩軸）已修：`issues` 模組 docstring 的「它們都只呼叫 `record_issue`」、`health_issues._settle` 手寫的收掉改用 `clear_by_system`、補 poller 問不到不算解除的測試。未處理：

- `Recorded` 用 `opened` 與 `held` 兩個 bool 表示三種結果（開了新的、更新了開著的、被忽略的擋下），`opened=True, held=True` 表示得出來但沒有路徑產生它；換成 enum 要動所有讀 `.opened` 的地方，判斷題，沒做。
- `issues` 模組 docstring〈先查再寫，沒有接 `IntegrityError`〉說「今天沒有兩個呼叫端寫同一種型別」，但 `unknown_torrent` 在這張票之前就有 poller 與對帳兩個生產者；兩個交易同時開同一筆時會撞 partial unique index。沒有 repro，沒動。
- 對帳的 `_check_unknown_torrents` 遇到被忽略的那筆也不重開，是靠 `record_issue` 結構上保證，沒有專門的測試（回驗那條經過同一個 `_Tally`，`(opened, updated) == (0, 0)` 有斷言）。
