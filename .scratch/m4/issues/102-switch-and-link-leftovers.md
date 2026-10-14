# 102 — 收尾（行為）：換台後下載中的 Job、既有換既有、Prowlarr 連結、空出空間

**Status:** done

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

- [x] 1、2：vitest 或整合測試守著，做變異驗證；playwright 實跑換台（用演練伺服器或隔離環境，**不准碰使用者的 `berth-local`**）
- [x] 3：附真服務上打開連結的結果（截圖或 URL 與頁面標題）；brief §20 補上來源
- [x] 4：pytest 守 sparse 檔的估算（Linux 上有效，Windows 上跳過要寫明理由）
- [x] 全部檢查、pytest、vitest、前端 e2e 綠；CHANGELOG、progress.md 已更新

## Comments

- **1 重現**：`test_setup_leftovers.TestDownloadsStillOnTheOldOne::test_after_the_switch_the_poller_opens_client_removed_for_them`——原本那一台上下到一半的那一筆，換到 `HOME` 之後第一輪 poller 就是 `client_removed` 並開了 Issue。**選「換台框照實說」**，不標成不再追蹤：那件 Issue 的「重新送單」送到的就是新那一台，是換台之後唯一的出路；標成不再追蹤要新加一個狀態，使用者也失去這條路。`Leftovers.in_flight`（`IN_CLIENT_STATES`，就是 poller 會開 `client_removed` 的那幾種；讀 Berth 自己的 Job，連不到原本那一台也列得出），`GET …/leftovers` 多 `in_flight`。換台框在做種那一句之後多一段「還沒下完的 N 筆例外，Berth 仍記著它們…」，用待處理頁的同一組詞（Issue 型別名、「重新送單」「承認移除」），下面列 Job 名字。
- **2**：「改位址」打了**另一個**位址（與後端同一種正規化：去頭尾空白與結尾的 `/`）時，同一份換台說明、留下的東西與移除勾選就地加在表單的送出鍵上方，「測試連線」就是確認——與套件內換成既有的那個確認區一樣（表單在確認區裡、按測試就是確認），沒有另開一層確認。只改憑證、打回原本那一個都不出現。Prowlarr 也走這條（後端一樣算換台），沒有移除勾選。整合測試補一條既有換既有、勾了移除，移除的是原本那一台的空分類。
- **2 的「同一台只換了 IP」照舊**：qBittorrent 的 WebAPI 沒有持久的實例識別碼（`appcontroller.h` 列出的端點裡沒有；`app/processInfo` 的 `launch_time` 2026-01 才加、重啟就變；IP 換了時舊位址多半連不到，沒得比；版本加 `save_path` 兩台預設安裝一模一樣）。寫進 brief §20.2〈同一台 qBittorrent 認不出來〉。後果照舊：Route 檢查作廢（自動重查）、已入庫 Job 詳情說「在原本那一台」。
- **3 實開**（隔離容器 `t102-prowlarr` linuxserver 2.6.5、`t102-qbit` 5.2.4，跑完已刪；截圖 `.playwright-mcp/t102/`）：Prowlarr `/#/settings/general` → 標題「Indexers - Prowlarr」（首頁，`prowlarr-hash-settings-general.png`）；`/settings/general` → 「General Settings - Prowlarr」（`prowlarr-settings-general.png`）；`/#/indexers` → 首頁（碰巧對）；`/indexers` → 「MIA」；`/` → 「Indexers - Prowlarr」（`prowlarr-root-indexers.png`）。qBittorrent 登入後 `/#/settings` 落在主畫面的 torrent 清單（`qbittorrent-hash-settings.png`），`client.js` 只讀 `#download=`。改成：索引站 `${webUrl}/`、介面登入 `${webUrl}/settings/general`（`serviceWeb.PROWLARR_PAGE`，事件頁也收進來）；qBittorrent 給 WebUI 本身，補法改說「工具 → 選項 → Web UI」。brief §20.14、§20.2 補來源。
- **4**：`fs.PathFacts.allocated`（`st_blocks` × 512），`deletion._measure` 的 `bytes` 與 `reclaimable` 改量它，所以 complete 那一側也一起變。**改了之後的意思**：估算與時間線的 `freed` 是刪掉之後真的回到檔案系統的區塊——下到一半的 sparse 檔照下載了多少算，已下完的檔以區塊取整（4 KiB 區塊上一個 10 位元組的檔算 4096）；btrfs / ZFS 開壓縮時是壓縮後的大小。`issues` 與 `reconcile` 比「兩邊是不是同一份」照舊用表觀大小 `size`。Windows 的 `os.stat` 沒有 `st_blocks`（等價的是 `GetCompressedFileSizeW`）；Berth 只在 Linux 容器裡跑，開發機上退回表觀大小，有一條測試守著這個退路。**Linux 實跑**（`python:3-slim` 容器、`uv sync`）：`test_fs.py` 與 `test_deletion.py` 86 條全過、不跳過；把 `reclaimable` 改回 `size`，sparse 那條紅。
- **實跑**（演練情境 `downloads`，port 8611，不碰 `berth-local`）：設定 → qBittorrent 選既有，換台框列出 `- 08`、`- 25` 兩筆還沒下完的（`p1-switch-in-flight-1280.png`）；換到 `http://192.168.1.10:8080` 之後「改位址」打 `http://192.168.1.11:8080`，表單裡出現換台說明、清單與勾選（`p2-readdress-1280.png`、`p2-readdress-390.png`），勾了送出的請求是 `{"origin":"existing","base_url":"http://192.168.1.11:8080",…,"remove_empty_categories":true}`；再打開打回同一個位址，什麼都不出現。限制同票 65：演練伺服器上新舊兩台是同一個替身物件。
- **變異驗證**：vitest——拿掉 `in_flight` 那一段三條紅；`readdressing` 固定 false 三條紅；拿掉「位址沒變」的比對一條紅；收窄成只有 qBittorrent，Prowlarr 那條紅。pytest——`_unreachable` 不帶 `in_flight` 時連不到那一條紅（紅燈先行時就是）。
- **驗證**：全部檢查綠；pytest 4006 passed、2 skipped（Windows 上的兩條 sparse，Linux 上另跑過）；vitest 1895 passed（審查之後改到的 `ServiceChoice`、i18n 再跑一次 116 條綠）；前端 e2e 35 passed。e2e 跑的時候 8491 被另一個 worktree（票 103）的演練伺服器佔著，沒停它，改用一份把所有 port 平移 +10000 的暫時設定檔跑完即刪。
- code-review 已處理：前端判斷換台只 `trim()`、後端還去結尾的 `/`，打 `http://nas:8080/` 會誤報換台（Standards、Spec 都抓到），改成同一種正規化並加進測試；做種那一句說「不再追蹤」、新那一段說會變成待處理，兩段矛盾（Spec），新那一段改成明說是例外；Prowlarr 的改位址沒有測試（Spec），補一條並做變異；`PathFacts` docstring 的「四個值」（Standards）；brief 的「只寫在 `PROWLARR_PAGE`」改成描述現況（Standards：沒有閘門守的宣稱）。
- code-review 沒處理的：Standards 說 `PathFacts.size` 沒人用了——不成立，`issues.py` 的「大小不同」拒絕與 `reconcile.py` 的 `inode_mismatch` 細節還在讀它。Spec 說改位址沒有另開確認框，偏離票面字面——照套件內換既有的同一種做法（表單在確認區裡、按測試就是確認），記進 progress.md 偏差。`ExistingForm.onAddress` 是可選參數（Standards 判斷題，自己也說可以接受）。
