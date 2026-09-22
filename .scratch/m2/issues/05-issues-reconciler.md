# 05 — `issues` 表 + 最小 reconciler + `/issues` 頁

**Status:** ready-for-agent

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

- [ ] 刪掉一個 library 檔 → `POST /reconcile` → `GET /issues` 有一條 `library_link_missing` →
      按「重新鏈接」之後檔案回來、Issue 是 `resolved`、帳本那一欄回 `ok`（整合測試走完整條）
- [ ] 同一個破壞連跑兩輪對帳只有一筆 `open`（冪等鍵），第二輪更新 `detail_json` 與 `detected_at`
- [ ] 三個 resolve 動作都到位：重新鏈接 / 承認刪除並清帳本 / 連 complete 一起刪（第三個走票 04
      的旗標，不是另一套刪除）
- [ ] `POST /reconcile` 回 202 帶 id；跑的時候再按回 409 `reconcile_running`；`GET /reconcile`
      看得到進度（哪一方比到哪、幾筆）
- [ ] qBittorrent 連不上時那一方**跳過並說出來**，沒有任何 Issue 被寫成「不見了」（整合測試）
- [ ] M1 的四種管線 Issue 從這一票起同時寫進 `issues`，且與事件共用同一個封閉集合（加一個型別
      到事件而沒加到表會讓 type check 或測試紅）
- [ ] `user` 登入時 `/issues/*` 與 `/reconcile` 全是 403
- [ ] `/issues` 頁：一列一件事、按得到動作；playwright 實跑一次修復，附截圖或文字結果
- [ ] lint、type、test 綠燈

## Comments
