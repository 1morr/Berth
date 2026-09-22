# 05 — `issues` 表 + 最小 reconciler + `/issues` 頁

**Status:** done

**Blocked by:** 04（`library_link_missing` 的「連 complete 一起刪」走 `delete_job` 的旗標；
`/issues`、`/reconcile` 的 admin 門禁沿用票 04 立起來的規則）

**讀:** plan §2.4（`issues` 那一段，含十一種型別與冪等鍵）、§3.2（`reconciler` 那一列）、§6（issues 群組）、§7（路由清單）、§11.3 的決定 3 與 5；brief §9.1、§9.5

## 做什麼

M0 / M1 等了兩輪的載體，**端到端的最小版**：刪掉一個 library 檔 → 按對帳 → 出現一條 Issue →
按「重新鏈接」修好。迴圈這一輪**只做 `library_link_missing`** 一種檢查，其餘十種在票 09；
形狀先立對，第二種才便宜。

**資料**：`issues` 表（§2.4 的欄位），`type` 是**十一種的封閉集合**——與 M1 `issue_detected`
事件用的 `IssueType` 共用同一份。冪等鍵 `(type, subject)`，`subject` 依型別取（§2.4 那一段逐型別
寫死了取哪一欄）：同一個 `(type, subject)` 只有一筆 `open`，再偵測到就更新 `detail_json` 與
`detected_at`。

**M1 的 `issue_detected` 事件改成同時寫一列 `issues`**。事件是歷史，Issue 是「要有人決定」的那一件，
四種管線型別（`missing_files` / `client_error` / `client_removed` / `jellyfin_item_unresolved`）
從這一票起兩邊都寫。

**端點**：`GET /issues`、`POST /issues/{id}/resolve`（`{action}`，動作是 brief §9.1 那一欄的封閉
集合）、`POST /issues/{id}/ignore`、`POST /reconcile`、`GET /reconcile`。

**一輪對帳是一個可觀察的工作**（§3.2）：`POST /reconcile` 回 **202** 並給這一輪的 id，
`GET /reconcile` 回上一輪與進行中的進度，上一輪還在跑時再按是 **409 `reconcile_running`**
——不排隊，排隊的那一輪看到的會是同一份磁碟。四方各自走完才寫下 Issue，任一方問不到
（qBittorrent 掛了、Route 目錄沒掛上）就跳過那一方並在這一輪的結果上說出來，**不把「問不到」
誤判成「不見了」**（brief §16.2）。

**`/issues` 是獨立頁**（決定 3），不是健康頁的一段：健康頁是唯讀診斷，issues 要按動作。新頁面，
所以先 `/impeccable shape` 再實作（專案 CLAUDE.md 的 UI 規則）——這一頁的清單與票 06 的 `/review`
是兩份不同的清單（issues 只有 Issue，review 是五類的統一佇列），但**一列一件事**的排法要一致，
shape 時把兩邊的關係說清楚。

**`ledger.status.target_missing` 與 `library_link_missing` 是同一件事的兩個角度**：帳本那一欄
是現況，Issue 是要有人決定的那一件；resolve 之後把帳本那一欄改回 `ok` 或刪掉那一列。

## 驗收

- [x] 刪掉一個 library 檔 → `POST /reconcile` → `GET /issues` 有一條 `library_link_missing` →
      按「重新鏈接」之後檔案回來、Issue 是 `resolved`、帳本那一欄回 `ok`（整合測試走完整條）
- [x] 同一個破壞連跑兩輪對帳只有一筆 `open`（冪等鍵），第二輪更新 `detail_json` 與 `detected_at`
- [x] 三個 resolve 動作都到位：重新鏈接 / 承認刪除並清帳本 / 連 complete 一起刪（第三個走票 04
      的旗標，不是另一套刪除）
- [x] `POST /reconcile` 回 202 帶 id；跑的時候再按回 409 `reconcile_running`；`GET /reconcile`
      看得到進度（哪一方比到哪、幾筆）
- [x] qBittorrent 連不上時那一方**跳過並說出來**，沒有任何 Issue 被寫成「不見了」（整合測試）
- [x] M1 的四種管線 Issue 從這一票起同時寫進 `issues`，且與事件共用同一個封閉集合（加一個型別
      到事件而沒加到表會讓 type check 或測試紅）
- [x] `user` 登入時 `/issues/*` 與 `/reconcile` 全是 403
- [x] `/issues` 頁：一列一件事、按得到動作；playwright 實跑一次修復，附截圖或文字結果
- [x] lint、type、test 綠燈

## Comments

- **`missing_files` 的冪等鍵改成 `job_hash`**（plan §2.4 原本列在「用路徑」那一組）。`SUBJECT_OF` 那條
  閘門在實作時當場抓到：它有**兩條偵測路徑**——Berth 自己比 complete 底下的檔案時知道少了哪幾個，
  而 qBittorrent 報 `missingFiles` 時手上一條路徑都沒有（多半正是因為它看不到那個掛載）。同一種型別
  的 subject 不可以看呼叫端而定。plan §2.4 與 progress.md 已同步。
- **`subject` 是一個存下來的欄位**，plan §2.4 的欄位表上沒有它：取出來的值要落在某處，partial unique
  index 才守得住冪等鍵。plan §2.4 已同步。
- **「連 complete 一起刪」四個旗標全勾，含 `purge`**。不 `purge` 的話帳本那幾列會讓下一輪對帳再開一批
  `library_link_missing`——使用者剛決定過的那一件會自己回來。拿掉 `purge` 讓兩條測試變紅（實跑確認）。
- **每日 04:00 的排程做了**（plan §3.2 的 `reconciler` 那一列），票上沒有它的驗收條件。它與
  `POST /reconcile` 按的是同一個 `ReconcileRunner`，所以「一次只有一輪」只有一份判斷。
- **留給票 09**：其餘十種檢查、它們的 `ISSUE_ACTIONS`（現在是空 tuple），以及
  `tests/unit/test_issue_types.py::test_the_only_type_with_actions_this_round_is_the_missing_link`
  ——那一條是**刻意會過期的**，票 09 加第二種型別時要跟著改，而改它的人正好會看到「新的那一種也要
  決定按得了什麼」。
- **留給票 06**：`/review` 做出來之後，把 `IssueRow` 與 `ReviewRow` 共用的那一列抽成 `QueueRow`
  （使用者 2026-09-22 拍板：先自建，有兩個真實案例再抽）。

### `/code-review` 的發現

兩軸各跑一次（Spec 與 Standards）。**修掉的六條**：

1. **`opened` / `updated` 數錯**（Spec）。原本從帳本的舊狀態推，而被 `ignore` 過的那一列仍然是
   `target_missing`——下一輪 `record_issue` 開的是新的一筆，報告卻說「更新 1 件」。改成由
   `record_issue` 回報它真的做了什麼（`Recorded.opened`），補 `TestWhatTheRunCounts` 兩條；
   把舊邏輯放回去會讓其中一條紅（`assert (0, 1) == (1, 0)`，實跑確認）。
2. **型別色塊塗紅**（Standards，硬性違規）。型別是**分類**不是狀態，DESIGN.md 的 The Role Is Not
   A State Rule 要中性色塊，而 The One Meaning Rule 說紅只代表阻擋。改成 `deck` 底 `ink` 字。
3. **render 期 `invalidateQueries`**（Standards）。`ReconcileBanner` 在 component body 裡失效查詢，
   會 refetch → 重繪 → 再失效地一直打 `/issues`。改成 `useEffect` 認「`last` 換了一輪」——
   每日 04:00 那一輪沒有人按，它開出來的東西一樣要出現。
4. **「Berth 的 torrent」判準寫了兩份**（Standards）。poller 與對帳問的是同一個問題（plan §3.2 的
   兩道篩子的聯集），抽成 `services/qbittorrent.managed()`，兩邊都改走它。
5. **整張帳本一輪讀兩次**（Standards）。`_countable` 與 `_check_library_links` 各跑一次
   `_entries_under`，連 `fs.is_within` 都算兩遍。問媒體庫那一方時讀一次，存進 `_Survey`。
6. **閘門宣稱指到不存在的檔案**（Spec）。`SUBJECT_OF` 與 `ISSUE_ACTIONS` 的註解寫
   `tests/unit/test_issue_subjects.py`，實際是 `test_issue_types.py`——不準的宣稱會讓下一個人
   不去檢查。順手把 `unknown_torrent` 的歸屬講清楚（brief §9.1 算它對帳七種，但今天寫它的是
   poller；票 09 之後兩個生產者共用同一個冪等鍵）。

另外移掉三個沒有呼叫端的東西：`_Survey.report()`、`services/issues.read_issue()`、
`ReconcileReport.running`（產品端用 `finished_at`，只有測試讀它）。

**看過但沒改的兩條**：

- **五種型別還沒有 producer**（Standards 列為硬性違規）：`source_missing` / `inode_mismatch` /
  `orphan_complete` / `unmanaged_library_file` / `job_without_files` 只出現在兩張表與 i18n。
  **保留**：十一種是票面要求（驗收第 6 條要「加一個型別而沒加到表就紅」），而那兩張表的涵蓋閘門
  正是為票 09 立的。i18n 那 20 條字串一起留——型別是封閉集合而畫面照它挑句子，票 09 補檢查時
  少一句會在畫面上露出一條 i18n key。
- **`unknown_torrent` 也寫進 `issues`**（Spec 列為範圍蔓延）：票面說「四種管線型別」，但它同樣是
  M1 已經在寫的 `issue_detected` 事件，而票面那一句是「M1 的 `issue_detected` 事件改成同時寫一列
  `issues`」。留著；`test_issue_types.py` 的兩個集合已改成照 brief §9.1 分。
