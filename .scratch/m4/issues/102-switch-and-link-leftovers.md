# 102 — 收尾（行為）：換台後下載中的 Job、既有換既有、Prowlarr 連結、空出空間

**Status:** ready-for-agent

**Blocked by:** None — can start immediately

**讀:** 票 65、73、74 的 Comments（下面每條都從那裡來）；brief §16.4；`berth/services/deletion.py`；`web/src/setup/` 的換台框（`ServiceChoice`、`LeftoverList`）

## 為什麼

票 65、73、74 收尾時各留下幾件沒修的事，使用者（2026-10-14）同意收成一張。每一條都要**先重現**；重現不出來的照實寫進 Comments，不硬修。

## 做什麼

1. **換台後還在下載中的 Job**（票 65）：
   - 換 qBittorrent 之後，torrent 留在原本那一台，新那一台找不到，poller 會開 `client_removed` 待處理。
   - 換台框只說「下載中的照樣下載」，沒說那幾筆之後會變成待處理。
   - 先重現，再決定兩種做法之一：換台框照實說出來（列出會變成待處理的幾筆），或換台時把那幾筆 Job 標成不再追蹤，不開 Issue。選了哪一種、為什麼，記進 progress.md「偏差與決定」。
2. **設定頁「改位址」從一台既有換到另一台既有**（票 65）：後端照樣當成換台（Route 檢查作廢），但不走換台框，看不到做種說明，也勾不了移除空分類。讓這條路也走換台框。
   - 同一台 qBittorrent 只是 IP 換了，Berth 也會當成換台。這一點要不要處理，先查有沒有可靠的辨認方法（例如 qBittorrent 的版本加上 `save_path`）；沒有就照舊，在 Comments 說明。
3. **Prowlarr、qBittorrent 的深層連結**（票 73）：`IndexerStep.tsx`、`IndexerSites.tsx`、`QbittorrentStep.tsx` 用了 `${webUrl}/#/indexers`、`/#/settings/general`、qBittorrent 的 `/#/settings`。Prowlarr 是 BrowserRouter，這類連結多半落在首頁。
   - 用真的 Prowlarr 與 qBittorrent（隔離環境）實際打開確認，再改成會落到正確頁面的寫法；查到的路徑補進 brief §20 並附來源。
4. **「可空出空間」對下載到一半的檔案偏大**（票 74）：現在用表觀大小 `st_size`，但 qBittorrent 下到一半的檔是 sparse 檔，實際佔的少很多（票 42 那一筆表觀 970 MB，實際約 192 MB）。改成用實際佔用（`st_blocks`；Windows 上要查等價做法）。complete 那一側同一條規則一起改。在 Comments 寫明改了之後估算的意思。

## 驗收

- [ ] 1、2：vitest 或整合測試守著，做變異驗證；playwright 實跑換台（用演練伺服器或隔離環境，**不准碰使用者的 `berth-local`**）
- [ ] 3：附真服務上打開連結的結果（截圖或 URL 與頁面標題）；brief §20 補上來源
- [ ] 4：pytest 守 sparse 檔的估算（Linux 上有效，Windows 上跳過要寫明理由）
- [ ] 全部檢查、pytest、vitest、前端 e2e 綠；CHANGELOG、progress.md 已更新
