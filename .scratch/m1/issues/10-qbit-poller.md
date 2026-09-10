# 10 — qbit_poller、SSE 與 Job 詳情時間線

**Status:** done

**Blocked by:** 09

**讀:** plan §3.1、§3.2（qbit_poller）、§6（events 群組）、§8.1、§11.2（T1.4）；
brief §5.1、§5.2、§20.2

## 做什麼

送單之後不用重整就看得到狀態與進度一路走到 `completed`；Job 詳情頁有時間線（brief §5.2 的事件）；
重啟 Berth 不丟狀態。

`qbit_poller` 用 `sync/maindata` 帶 rid 做增量，只看本系統 category 的 torrent，驅動 plan §3.1 中
由客戶端狀態觸發的每一個轉換。轉換一律 compare-and-set，每個 job 另有程序內的 `asyncio.Lock`。

順便解掉 plan T1.9 的第四條：**qBittorrent 的 403 要分得出「帳密不對」與「IP 被封」**——4.4.x
連續登入失敗會封 IP 且同樣回 403，現在被顯示成「帳密不對」（plan §8.1）。

`issues` 表在 M2 才建，所以本票的「無主 torrent」先寫 event；這是相對 plan §3.2 字面的偏差，
要記在 `docs/progress.md`。

## 驗收

- [x] `qbit_poller` 由 lifespan 啟動、關閉時 cancel 並 await，不留 pending task
- [x] 間隔：有活躍 job 5s、否則 30s、連續失敗退避到 5 分鐘
- [x] plan §3.1 中由客戶端狀態觸發的轉換全部實作：`metadata_ready`、`downloading`、`stalled`、
      `missing_files`、`client_error`、`client_removed`、`completed`
- [x] 轉換一律 compare-and-set（影響 0 列即放棄），有並發測試
- [x] `metadata_ready` 時建立 `job_files`（`torrents/files[].name` 相對 `save_path`，先正規化尾斜線）
- [x] 完成判定依 brief §20.2，4.4 與 5.x 兩個版本各有契約測試
- [x] 進度事件每跨 25% 一筆，不刷屏
- [x] `GET /api/events/stream`（SSE）推送 job 狀態與進度；前端據此讓相關 query 失效
- [x] 送單到完成的狀態在 UI 即時更新、不用重整（playwright 實跑並附結果）
- [x] 重啟 Berth 之後狀態不丟：由 DB 與下一輪 maindata 補上（實跑驗證）
- [x] 無主 torrent 記一筆 event 並在 Job 列表或健康頁看得見（`issues` 表留 M2，偏差記進 progress.md）
- [x] qBittorrent 的 403 分得出「帳密不對」與「IP 被封」，兩種都有測試與可行動的訊息
- [x] Job 詳情頁的時間線顯示 brief §5.2 的事件，走 `/impeccable shape`
- [x] 對比 ≥ 4.5:1；390px 窄版可用；zh-Hant 與 en 並列
- [x] lint / type / test 全綠並貼指令輸出

## 實跑紀錄

**環境**：真的 `lscr.io/linuxserver/qbittorrent:5.2.3`（發佈在 8080——它的 Host 檢查連 port 都比對）
＋ `scripts/fake_setup_server.py --scenario poll`（真的 API、真的資料庫、真的前端 build、真的 poller，
只有 Jellyfin / Prowlarr 是替身）。那一份 torrent 的資料先寫進 category 的 save path，所以
qBittorrent 校驗完就是「完成」——狀態是它算出來的，不是擺出來的。

- **送單到完成不重整**：`/jobs` 開著不動，那一列自己走過三個樣子——
  `(尚未出現)` → `已取得檔案清單 · 大小 39 KB · 進度 —`（+5.8 秒）→
  `下載完成 · 大小 39 KB · 進度 100%`（+10.8 秒）。全程
  `performance.getEntriesByType('navigation').length === 1`（只有最初那一次載入）。
  後端 log 的 `sync/maindata?rid=` 逐輪遞增，增量真的成立。
- **重啟不丟狀態**：同一個 config-root 重開，`/jobs` 仍是 `下載完成 · 進度 100%`，展開的時間線
  仍是 `created → submitted → metadata_received → completed` 四筆，各自帶著自己那幾格
  （`route=anime`、`berth-anime` + `/downloads/complete/anime`、`2 個檔案 · 39 KB`、`39 KB`）。
- **無主 torrent**：把資料庫清掉、torrent 留在 qBittorrent，下一輪就寫了一筆
  `issue_detected(unknown_torrent)`，健康頁的「下載迴圈」列出 `stalledUP · 發佈名 · berth-anime · 短 hash`。
- **重試**：qBittorrent 已經有同一個 hash 時送單得到 `409`，那一列是 `送單失敗` + 原文；
  在 qBittorrent 上刪掉之後按「重新送單」就回到 `已送出`。
- **窄版**：390×844 的健康頁，`scrollWidth - clientWidth === 0`（沒有頁面層級橫向捲動），
  剖面塌成單欄；zh-Hant 與 en 兩種語言都跑過。1440px 的健康頁上「下載迴圈」排在三個服務
  之後、Route 清單之前。

**code-review 之後又改了什麼**（都在同一個 commit 裡，改完重跑了整段實跑）：
被封的 IP 現在一路傳到畫面上（`DetectionReason.IP_BANNED` + `ServiceHealth.banned` + 兩種語言的
下一步）；推播改成「一筆 job 一輪最多一個訊號，而且只有真的變了才推」；無主 torrent 那一列的
`client_state` 從 `.label` 換成 `.value`（`.label` 會把 `stalledDL` 大寫成 `STALLEDDL`）；
時間線的事件型別收成一份清單，少寫一個 renderer 會在 `tsc` 就紅。

## Comments

這一票**沒有做**、或做法與票上字面不同的地方（每一條都記在 `docs/progress.md` 的「偏差與決定」）：

- **pre-plan 不在這一票**。plan §3.1 的 `metadata_ready` 副作用有兩半，`plans` 表到票 11 才建，
  所以這裡只做前半（`job_files` + `metadata_received`）。
- **`issues` 表留給 M2**。無主 torrent、`missing_files`、`client_error`、`client_removed` 在 M1 的
  載體是一筆 `issue_detected` 事件（`IssueType` 四個值），加上健康頁那份「現在還在不在」的清單。
- **健康檢查的兩條 M0 技術債仍未做**（plan §11.3 已記）：磁碟空間的門檻判定、媒體庫掛 TVDB 插件的
  警告要成為一則 Issue。兩條都在等 `issues` 這個載體。
- **`poll` 演練情境在 Windows 上會留下一個 `C:\downloads`**（容器路徑在那裡是「目前磁碟機的根目錄
  底下」）。跑完要刪掉，否則 `tests/integration/test_setup_routes.py` 裡「Berth 看不到那條 save path」
  的兩條會誤判成通過。已寫進 README 的那一段。
- **登入時的一個既有缺陷**（票 07 的範圍，這一票只是撞到）：同一個新使用者兩次登入同時進來時，
  `users.jellyfin_user_id` 的 unique 會讓其中一次變成 500。實跑時因為連按兩次登入而觸發，
  `add_download` 的主鍵撞車已經有對應的處理（票 09），這一支還沒有。
- **本機的 11 個測試失敗與這一票無關**：`tests/unit/test_entrypoint.py` 與
  `tests/unit/test_qbittorrent_preseed.py` 用 `shutil.which("bash")`，而這台 Windows 上它解到
  `C:\WINDOWS\system32\bash.exe`（WSL 的殼）並回 127。在 `8ac6a32`（本票開工點）上 stash 掉所有
  變更之後跑同樣兩個檔案，一樣是那 11 個失敗。
