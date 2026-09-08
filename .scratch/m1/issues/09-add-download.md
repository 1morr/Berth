# 09 — 送單、Job 與下載列表頁

**Status:** ready-for-agent

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

- [ ] `jobs` 與 `job_files` 表與 migration，欄位依 plan §2.3
- [ ] `POST /api/jobs`（`{source, media, route}`）建 job（`requested`）→ qBittorrent 接受 → `submitted`，
      兩個轉換各寫一筆 event
- [ ] qBittorrent 上出現正確的 category 與 save path（`<complete root>/<route slug>`）
- [ ] 參數依版本：`stopped` / `paused` 的選擇有版本矩陣測試；`contentLayout=Original`、`autoTMM=true`、
      `tags=berth`
- [ ] 同 hash 重複送單回傳既有 job，不重複送單（plan §3.3）
- [ ] qBittorrent 拒絕或不可達 → `submit_failed` 並顯示原因；可手動重試回 `requested`
- [ ] Route 的健康是紅的時候擋下送單並說明為什麼（brief §4.4：紅的 Route 送單一定失敗）
- [ ] `GET /jobs`、`GET /jobs/{hash}`、`GET /jobs/{hash}/events`
- [ ] 下載列表頁顯示每筆 Job 的狀態、進度、Route、trigger，可點進去
- [ ] 在 job 上下文裡的每一行 log 都帶 job id（plan T1.9），有測試證明
- [ ] 下載列表頁走 `/impeccable shape`；playwright 實跑；對比 ≥ 4.5:1；390px 窄版可用
- [ ] zh-Hant 與 en 並列；lint / type / test 全綠並貼指令輸出
