# 10 — `reimport` + `berth rebuild-ledger`

**Status:** ready-for-agent

**Blocked by:** 04（`POST /jobs/{hash}/reimport` 的方法層級門禁）、05（`rebuild-ledger` 配不到的要建 `unmanaged_library_file` Issue）、09（三種 Issue 的偵測與動作表）

**讀:** plan §6（jobs 群組）、§4.2（核心型別）、§5（命名引擎，反解目標路徑）、§11.3 的決定 9；brief §9.3（重新入庫）、§4.1（三層路徑）

## 做什麼

M2 驗收第一條：**刪掉 library 之後一鍵重建**。兩條路徑，一條走 API 一條走 CLI。

**`POST /jobs/{hash}/reimport`**：以那一筆 Job 的 complete 目錄重跑 planning → review/importing。
**目錄版**：Import Source 可以是「complete 內任一資料夾」，**不要求 torrent 仍存在**（brief §9.3）。
帳本以來源相對路徑冪等，所以「刪了 library、保留 complete、再重新入庫」是一鍵動作。

**`berth rebuild-ledger`**：從 library 的 inode 反查 complete。**配得上的重建完整一列**——季集與
Tags 從目標路徑反解（命名是純函式，反解用同一份規則）。**配不到的一律建
`unmanaged_library_file` Issue，不猜**（決定 9）。

這兩件是同一張票，因為它們是同一個問題的兩個入口：帳本沒了要怎麼從磁碟上的事實把它長回來。

**票 09 移過來的三顆「認領」**（2026-09-23 使用者拍板）：它們用的正是上面兩個原語，在票 09 先做一份
會變成兩條入庫路徑。票 09 已經偵測得出這三種，現在只按得了「忽略」：

- `orphan_complete`「重新入庫（adopt）」：以那個目錄為 Import Source 走目錄版 `reimport`。
- `unknown_torrent`「認領（建 Job 並解析）」：替 qBittorrent 上那一筆建 Job，交給 poller 與規劃器。
- `unmanaged_library_file`「認領進帳本」：單一檔案的 `rebuild-ledger`——配得上的長回一列，配不到的
  照舊只列出。**這一顆不刪任何東西**（`ACTION_DELETES`，`tests/unit/test_issue_types.py` 守著）。

加進 `ISSUE_ACTIONS` 時 `test_issue_types.py::test_what_each_type_offers_this_round` 會紅（刻意會過期），
`web/src/issues/IssueRow.tsx` 的 `CONFIRM` 總表也會在 `tsc` 紅。

## 驗收

- [ ] 刪掉整個 library 目錄之後：`reimport` 目錄版一鍵重建，檔案回到 library、帳本重新長出來、
      Jellyfin 掃得到（整合測試走完整條，這是 M2 驗收第一條）
- [ ] torrent 已經不在 qBittorrent 時 `reimport` 照樣走得完（brief §9.3）
- [ ] 重複 `reimport` 同一個目錄不會產生第二份帳本列（以來源相對路徑冪等）
- [ ] `berth rebuild-ledger` 配得上的重建完整一列：季、集、Tags 都從目標路徑反解出來，且與命名
      函式的輸出一致（測試以同一份規則往返斷言）
- [ ] 配不到的**一筆都不猜**：全部變成 `unmanaged_library_file` Issue（測試造一個反解不出來的
      檔案，斷言沒有帳本列被寫出來）
- [ ] CLI 子命令在 README 有一節（專案 CLAUDE.md：README 是指令的單一來源）
- [ ] `user` 登入時 `POST /jobs/{hash}/reimport` 是 403，而 `GET /jobs` 照常
- [ ] 三顆認領按下去真的修好：`orphan_complete` 的目錄入庫、`unknown_torrent` 有了 Job、
      `unmanaged_library_file` 長回帳本一列（各一個整合測試，下一輪對帳不再開同一件）
- [ ] lint、type、test 綠燈

## Comments
