# 09 — 送單、Job 與下載列表頁

**Status:** done

**Blocked by:** 08

**讀:** plan §2.3、§3.1（前三列）、§3.3、§6（jobs 群組）、§8.1、§11.2（T1.3、T1.9 第二條）；
brief §5.1、§5.2、§16.2（結構化日誌）

## 做什麼

從結果表選一筆 torrent、選一條 Route，送進 qBittorrent：Job 建立、qBittorrent 上出現正確的
category 與 save path、下載列表頁看得到這筆 Job。

帶進來的東西：`jobs` 與 `job_files` 表、`add_download` 命令、jobs 群組的讀取端點、下載列表頁。
另外把 plan T1.9 的**結構化日誌帶 job id** 一起做掉——Job 在這一票誕生，之後的迴圈票（10、11、12）
沿用同一個上下文。

qBittorrent 的參數依版本決定（API ≥ 2.11 用 `stopped`，否則 `paused`）。**這是必要條件**：送錯的
參數會被靜默忽略，torrent 就這樣開始下載（brief §20.7）。

## 驗收

- [x] `jobs` 與 `job_files` 表與 migration，欄位依 plan §2.3
- [x] `POST /api/jobs`（`{source, media, route}`）建 job（`requested`）→ qBittorrent 接受 → `submitted`，
      兩個轉換各寫一筆 event
- [x] qBittorrent 上出現正確的 category 與 save path（`<complete root>/<route slug>`）
- [x] 參數依版本：`stopped` / `paused` 的選擇有版本矩陣測試；`contentLayout=Original`、`autoTMM=true`、
      `tags=berth`
- [x] 同 hash 重複送單回傳既有 job，不重複送單（plan §3.3）
- [x] **送單確認要印出資料夾名，成功時凍結它**（票 04b、plan §5、brief §4.5）：送單前那串字還跟著
      TMDB 的標題走，`add_download` 成功那一刻寫死在 `media.folder_name`，之後 refresh 不再動它；
      已經凍結過的作品第二次送單不重凍。`media.default_route_id` 同時寫成「上次用的」
- [x] **`tracked` 以 `EXISTS(jobs)` 推導**（票 04b、`CONTEXT.md`），不是欄位：詳情頁與探索牆的
      卡片狀態都讀這一份推導（票 12 的帳本與 M3 的 Rule 之後加進同一個推導）
- [x] qBittorrent 拒絕或不可達 → `submit_failed` 並顯示原因；可手動重試回 `requested`
- [x] Route 的健康是紅的時候擋下送單並說明為什麼（brief §4.4：紅的 Route 送單一定失敗）
- [x] `GET /jobs`、`GET /jobs/{hash}`、`GET /jobs/{hash}/events`
- [x] 下載列表頁顯示每筆 Job 的狀態、進度、Route、trigger，可點進去
- [x] 在 job 上下文裡的每一行 log 都帶 job id（plan T1.9），有測試證明
- [x] 下載列表頁走 `/impeccable shape`；playwright 實跑；對比 ≥ 4.5:1；390px 窄版可用
- [x] zh-Hant 與 en 並列；lint / type / test 全綠並貼指令輸出

## Comments

- **`torrents/add` 的成功形狀依版本判定**，推翻 brief §20.2 記的「一律回 200 `Ok.`」。2026-09-10
  對真的 5.2.3 與 4.4.5 各錄一輪：5.2.3 成功回一份 JSON 摘要。**這個缺陷是實跑當場抓到的**——
  單元測試與替身都看不見它，因為兩者驗的都是我們送出去的那一份表單。已更正 brief §20.2 / §20.7、
  plan §8.1 與 `docs/research/m0-experiments.md`，並錄了五份 fixture。
- **送單前 Berth 自己抓 torrent**（新的 `adapters/torrent.py`）。plan §8.1 原本只寫送參數。
  理由在 progress.md 的偏差條目：`jobs.hash` 是主鍵而索引站不一定報 hash，而交網址給
  `torrents/add` 是背景抓取、失敗永遠沒有下文（實測 `202` + `pending_count`）。
- **`/jobs/:hash` 這一票不做**（使用者拍板）：時間線就地展開在列裡。plan §7 的那條路徑留給
  T1.7 的完整 Job 詳情（檔案清單、Plan、刪除範圍）。
- **`DELETE /jobs/{hash}` 與 `POST /jobs/{hash}/replan` / `reimport` 沒做**：plan §6 的 jobs 群組
  列了它們，但刪除範圍是 M2（brief §9.2）、replan 與 reimport 要等 Plan 存在（票 11、M2）。
- **進度與大小這一票永遠是 `—`**：`torrents/info` 要等票 10 的 poller。欄位現在就在，值回來時
  同一個位置開始跳數字，版面不重排。
- **`job_files` 只建表**：第一批列由票 10 的 `metadata_ready` 寫。
- 送單失敗那一列在畫面上停在 `submit_failed` 直到有人按重試——**沒有自動重試**（plan §3.1 寫的
  就是「可手動重試」）。
