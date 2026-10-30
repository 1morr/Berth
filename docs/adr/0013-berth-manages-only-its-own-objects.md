# 接管＝只建立與管理 Berth 擁有的物件，不碰既有服務的全域偏好與帳密

起因：`berth-lab` 實測，使用者自己的 Prowlarr 還沒加索引站就被判成套件內，登入被覆寫成第 1 步的帳密；既有 qBittorrent 的全域下載路徑被改成 Berth 的目錄。決定（Sonarr / Radarr 對下載器的慣例，2026-10-06 D1 定稿）：

- **Berth 擁有的物件**才建立與管理：Jellyfin API key「Berth」、`berth-*` 分類、Berth 路徑、使用者確認加入的索引站、使用者在頁 3 勾了「新建一個媒體庫」的那一個媒體庫（E1）。全域偏好與帳密不碰。套件內與既有共用這條，差別只在套件內由 Berth 讓它有人登得進去（Jellyfin 管理員、介面登入、白名單、掛載的 key）。
- **套件內 qBittorrent 也不寫三個全域鍵**（`save_path`、`auto_tmm_enabled`、`category_changed_tmm_enabled`）：它們不影響 Berth，留著只讓 Route 為了 Berth 不用的路徑轉紅（D2）。
- **既有 Prowlarr 也能加公開站**（推翻原本「不替既有 Prowlarr 加站」）：審查時接一台 0 站的既有 Prowlarr 被標「已完成」、精靈裡加不了站，而零站的 Berth 什麼都搜不到。0 站時頁 4 待處理；加站走同一套「推薦站預設不勾、先測試、通過才勾、按一次加入」，畫面寫清楚會加進哪一台、哪幾站。**移除交給 Prowlarr 自己的介面**，介面登入只屬於套件內。
- **換一台 qBittorrent / Prowlarr 時**列出 Berth 在舊那台建的東西，可一鍵移除 Berth 建的空分類（D6）。
- **Jellyfin 掃描只刷新 Berth 寫入的那個媒體庫**；沒有可用的單一媒體庫端點時退而全庫掃描，並寫進 brief §16.4 物件表與既有服務卡片（E2）。
- **一套服務只配一個 Berth**：兩個 Berth 接同一台 qBittorrent / Jellyfin 時共用 `berth-*` 分類與「Berth」API key，不區分——重裝 Berth 接回原本的服務時沿用正是要的行為；*arr 也不替接同一台的多個實例自動分開。

來源：brief §19 舊列「既有服務不被改動」「既有 Prowlarr 也能加公開站」「一套服務只配一個 Berth」「精靈審計後的八項」D1、D2、D6、「第四輪可用性審計的八項」E1、E2（原文在 `docs/archive/m3.md`、`docs/archive/m4.md`）；`docs/research/wizard-audit-2026-10-06.md`、`docs/research/wizard-qa-2026-10-01.md`。
