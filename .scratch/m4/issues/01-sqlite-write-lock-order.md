# 01 — SQLite 寫鎖：加鎖順序與握著寫交易打網路

**Status:** done

**Blocked by:** None — can start immediately

**讀:** plan §11.5「M4 之前先做的修補」、§1.1（單一程序）、§3.2（背景迴圈）、§3.3（冪等與重入）；progress.md 2026-09-26「M3 後的全面審查」那一行

## 為什麼

2026-09-26 試跑（main `82d9cd7`）：一個 Mikan MyBangumi 綁定後 11 分鐘內送出 144 個 torrent，其中一筆的
pre-plan 在 `INSERT INTO plans` 爆 `sqlite3.OperationalError: database is locked`（事件 `round_failed`）。
WAL 與 `busy_timeout=5000` 都開著（`berth/db/engine.py:21,38-40`），所以是有人把寫鎖握超過 5 秒。

讀程式碼找到的成因（還沒 repro，第一步就是做出來）：

- **兩把鎖順序相反**。qbit poller 一整輪一個交易（`berth/services/downloads.py:176-210`，`:210` 才 commit）：
  第一筆狀態轉換之後就握著 SQLite 寫鎖，接著逐筆 `async with job_lock(job.hash)`（`:200`），`submitted`
  那幾筆還在鎖裡打 qBittorrent `client.files()`（`:482`）。planner 反過來：`guarded` 先拿 `job_lock`
  （`berth/services/jobs.py:515`），再在 `_preplan → _store` 寫 plans（`berth/services/plan.py:356`、`:846`）。
  planner 握著 Y 的 `job_lock` 等寫鎖、poller 握著寫鎖等 Y 的 `job_lock`，planner 等滿 5 秒就爆。
- **握著寫交易打網路**（Mikan 抓取逾時 30 秒）：`rss._record` 在 flush（`berth/services/rss.py:662`）之後
  還逐筆抓單集頁（`_series_key`，`:686-702`）；`bind_series`（`:1408`）的查詢 autoflush 之後才 `_backfill`
  抓單一 feed；`deletion` 先轉 `removed` 再打 qBittorrent 移除；`jobs._resubmit`（`jobs.py:~403`）先轉
  `requested` 再抓 .torrent、送 qBittorrent。plan §3.2 自己寫過「票 14b 的教訓」，這幾處沒跟上。
- **錯誤掛著不走**：rollback 之後沒有 Plan，下一輪 `_estimable`（`plan.py:271`）會重算，但 `job.error`
  只有狀態轉換會清（`jobs.py:~820`）。qBittorrent 排隊中的那一筆 progress 一直是 0、轉不到 `downloading`，
  畫面上它一直帶著 `database is locked`——試跑重啟後仍是如此。

## 做什麼

1. **先 repro**：整合測試讓 poller 一輪（Fake qBittorrent，`files()` 慢一點）與 planner 同時跑，重現
   `database is locked`；紅燈才動手。
2. 定一條寫交易紀律並寫進 plan §3.3：**先拿 `job_lock`、再開寫；網路呼叫不在寫交易裡**。poller 逐筆 commit
   或先把要動的 Job 的鎖拿齊再寫，擇一並寫理由。上面列的四處抓取移到交易外（或抓完再寫）。
3. `round_failed` 之後，那一筆下一次成功的一輪（不只是狀態轉換）要清掉 `job.error` 並在時間線留一筆。

## 驗收

- [x] 併發 repro 的整合測試：修之前紅、修之後綠（兩者都貼輸出）
- [x] 握鎖打網路的四處各有一條測試或一條閘門守著（例如在 Fake 的網路呼叫裡斷言 session 沒有待寫的改動 / 不在交易中）；閘門要做檔內雙向變異
- [x] pre-plan 失敗後下一輪成功：`job.error` 清空、時間線有一筆（整合測試）
- [x] plan §3.3 寫明交易紀律；§3.2 的「票 14b 的教訓」與它一致
- [x] lint、type、test 綠燈

## Comments

**紅燈（修之前）**：`test_write_discipline.py` 7 failed / 3 passed；併發那一條的原文是
`sqlite3.OperationalError: database is locked … [SQL: INSERT INTO plans …]`，與試跑同一句。修之後 12 passed
（code-review 之後補了鎖順序與每日補漏兩條）。鎖順序那一條另以「保留預抓 `files()`、改回握著寫交易逐筆拿鎖」
的變異驗過會紅（`database is locked`）；pre-plan 那一條在 `test_plan.py`，停掉 `_note_round_recovery` 時紅。

**選擇**：poller 是「網路先問完 → 照 hash 拿齊鎖 → 一個交易寫完」，不是逐筆 commit，理由在 plan §3.3 與
progress.md 偏差。時間線用既有的 `recovered`（`from = round_failed`），沒有新事件型別。

code-review 已處理：`_note_round_recovery` 包 try/except（兩個軸都抓到：它的 commit 撞鎖會衝出 `guarded`）；
補鎖順序與每日補漏的閘門；`poll_downloads` 與 `delete_job` docstring 的不實之處；`subscribe_mikan` 改呼叫
`_backfill`；`type: ignore` 補理由；CHANGELOG 與 progress.md。

未處理（判斷題）：
- `rss._record` 的 `keys` 與 `known` 兩者互斥卻是兩個可選參數（Standards）。改成各自解出 Series 再交進來要動
  三個呼叫端，收益小，留著。
- `_read_season` 回 `tuple[FeedItem, ...] | str`，呼叫端 `isinstance` 分支（Standards）：沿用舊 `_backfill`
  回原文字串的形狀。
- `LISTED_STATES` 不含 `missing_files` / `client_error`：接回時落在 `submitted` 的那一種晚一輪建清單（Spec，
  已記在 plan §3.3 與 progress 偏差）。
- 刪除的 CAS 在移除 torrent 之後：沒拿鎖改狀態的寫者會造成半套（Spec）。目前每一條改 Job 狀態的路都拿鎖，
  docstring 與 progress 偏差已寫明。
- 本票沒碰到的同類：`_plan` 的 TMDB 刷新（`snapshot_for_planning` → `_load`）與 mediainfo 是否在寫交易之後
  才跑沒有閘門；importer 的 Jellyfin 通知同。有 repro 再開票。
