# 03 — 大批送單的防護：磁碟門檻算在途量、暫時失敗的送單有限重試

**Status:** done

**Blocked by:** 01（送單路徑的交易紀律在那張票定）

**讀:** plan §11.5「M4 之前先做的修補」、§3.1（`requested` / `submit_failed`）、§3.2（`health_checker` 的磁碟門檻、請求預算）；brief §15（補舊集是預設）；`.scratch/m3/issues/04-submit-gates.md`、`12-mikan-backfill.md`、`20-request-budget.md`、`21-m3-acceptance.md` 的 Comments（真站一輪的 `ReadTimeout`）

## 為什麼

補舊集整部送出是 brief §15 的決定（有把握就自動綁定、預設補齊），不改。改的是它一次送一百多個時少的兩道防護：

- **磁碟門檻只看當下剩多少**：`check_disk`（`berth/services/jobs.py:625-650`）量 incomplete 的剩餘空間，
  不扣已送出、還沒下完的量。2026-09-26 試跑一次送 144 個，每一個送單當下都過門檻，磁碟要到下載途中才滿，
  變成一批 `client_error`。
- **暫時失敗的送單沒人接**：M3 票 21 真站一輪一次送近兩百個時，qBittorrent 在
  `GET /api/v2/torrents/categories` 回 `ReadTimeout`，那一筆停在 `submit_failed`——沒送進 qBittorrent，
  票 02 的 poller 認回接不到，只能人按重試（原記在 plan §11.4 結尾，這張票接手）。qBittorrent 整個掛掉時
  RSS 的每一筆也都長成 `submit_failed`（`rss._submit`），無人值守一次停機留下上百筆要逐筆按。

## 做什麼

1. **在途量**：門檻比的是「剩餘空間 − 在途 Job 還沒下完的量」。在途是 `submitted` / `metadata_ready` /
   `downloading` 的 Job：有 `total_size` 用 `total_size × (1 − progress)`，還沒有的用送單時知道的大小
   （RSS Item 的 `size`、搜尋結果的大小），都不知道的不算並在 log 說。拒絕理由沿用 `low_disk_space`，
   訊息說得出在途多少。
2. **有限重試**：`submit_failed` 的原因是暫時性的（逾時、連不上、5xx）時，由既有的迴圈自動重送，退避、
   次數有上限（照 plan §3.2 其他迴圈的退避形狀）；用完才停下等人，Job 的時間線逐次記。非暫時性的
   （.torrent 404、qBittorrent 明確拒絕）照舊直接等人。暫時與否的分類寫進 plan §3.1。
3. 不做：每次綁定或每輪送單的**數量上限**——qBittorrent 自己的佇列（預設同時 3 個）已經排得住，
   試跑 130 個 `queuedDL` 沒有造成錯誤；失效條件是「送單數量本身弄壞了什麼」，有 repro 再開。
   **.torrent 下載要不要算進站台請求預算**（M3 票 20 刻意不算）開工時先問使用者，答案寫進 plan §3.2。

## 驗收

- [x] 在途量：剩餘空間夠一個、不夠兩個時，第二個送單被 `low_disk_space` 擋下，訊息帶在途量（整合測試，雙向）
- [x] 暫時失敗的 `submit_failed` 在上限內自動重送成功；用完上限停下；非暫時性的不重送（整合測試，Fake qBittorrent 的逾時與 404 各一）
- [x] qBittorrent 停機期間 RSS 送出的那一批，服務回來之後不需要人按就接上（整合測試）
- [x] plan §3.1、§3.2 與使用者對 .torrent 預算的決定同步
- [x] lint、type、test 綠燈

## Comments

- 2026-09-27 開工時問使用者 `.torrent` 要不要進請求預算：**不算，維持現狀**（照 Prowlarr 的 Grab / Query 分開）。寫進 plan §3.2。
- 驗收第二條的「Fake qBittorrent 的逾時與 404 各一」：qBittorrent 明確拒絕用 415（`torrents/add` 的真實拒絕碼），404 打在重送時抓的 `.torrent`；另補 `.torrent` 5xx 照樣排下一次。
- 票面之外的兩個決定（plan §3.1 已改）：啟動時被打斷的送單（`fail_interrupted`）歸暫時、自動重送，推翻 M3 票 02「等人重試」；`stalled` 算在途。
- UI：時間線在暫時失敗那一筆多一句「第 n 次沒送成，自動再送：<相對時間>」或「送了 n 次都沒成，不再自動送」。playwright 對 Fake 後端（`rss` 情境、手放兩筆事件）實跑過，zh-Hant 兩種句子都對。
- code-review 已處理：一輪遇到第一筆又失敗就收手（原本一整批會在同一刻各燒一次次數）、次數在拿到 `job_lock` 之後重讀（等鎖時被人按過的重試不被蓋掉）、補 `.torrent` 5xx 與逐次退避間隔的測試、`resubmit_due` 改名 `retry_due`（`resubmit_job` 是 Issue 的重新送單，一詞兩義）、重試前提抽成 `_retry_target`。
- code-review **未處理**（判斷題或沒有 repro）：
  - `_fail` 以牆上時鐘算 `retry_at`、`retry_due` 拿 poller 注入的 `now` 比；正式環境兩者同源，測試以 `_later()` 對齊。要一致得把 `now` 穿過所有 `_fail` 呼叫端。
  - 暫時與否在 `_resubmit` 沿 `failure.__cause__` 回推（`_resolve` 包成 `JobRejectedError`）；可改成例外自帶 `transient`（同 `rss._LookupError`）。
  - 排程存在事件 payload 的字串鍵（`attempt`、`retry_at`），後端寫、後端讀、前端讀三處；RSS 的 `lookup_retry` 叫 `at`，命名不一致。
  - `IN_FLIGHT`（`services/jobs.py`）與 `IN_CLIENT_STATES`（`services/downloads.py`）是同一組狀態；`downloads` import `jobs`，反過來會循環，所以分兩份。
  - `JobSource.size` 以 `0` 表示未知、API 用 `null`，兩個呼叫端各轉一次。
  - 重啟時被打斷的那一筆 `attempt` 從 1 重數：程序反覆崩潰時上限被繞過。沒有 repro。
  - `_due_retries` 每一輪讀所有 `submit_failed` Job 的全部 `submit_failed` 事件，含永遠不會自動重送的舊案；量大了再加條件。
  - 時間線上被磁碟、Route 擋著或 qBittorrent 停機時，「自動再送：」顯示一個已經過去的時刻，看不出它正被擋著。
  - 重送在 poller 的那一輪裡依序跑，一批都成功時這段時間 poll 停著（一筆約一次 `.torrent` + 一次 `torrents/add`）。
