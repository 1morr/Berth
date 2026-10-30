# 精靈每個服務由使用者手動選「套件內」或「既有」，不偵測；精靈只管第一次

2026-09-26 的做法是只有 compose 主機名上探到的才可能是套件內、其餘泊位偵測。使用者試跑全新環境後 2026-09-29 推翻：

- **Jellyfin、qBittorrent、Prowlarr 各一頁，進頁先手動選**；選擇存下來、選完要測試。選了套件內而 compose 沒起那個服務時，說出怎麼補 `COMPOSE_PROFILES`；套件內但已初始化過改成登入。慣例照 Seerr 與 Sonarr / Radarr 的「手動填 → Test → Save」、TRaSH 的單一 `/data`（brief §20.14）。
- **不做 remote path mapping**，把「既有服務要與 Berth 在同一台主機、把同一個父目錄掛在同一個容器路徑」講清楚；套件容器名用 `berth-*` 前綴。
- **只有 Berth 時，套件內卡片進頁只查主機名、不對服務發請求**，不預選、不停用。
- **套件內 qBittorrent / Prowlarr 的介面登入**預設沿用 Jellyfin 帳密；Berth 寫進那兩台的介面密碼只存加鹽雜湊（沿用時它就是 Jellyfin 密碼，存明文會推翻「資料庫裡沒有擁有者的明文密碼」）。
- **精靈只管第一次，跑完之後的修改在設定頁**：設定頁按五個泊位分頁（Jellyfin、qBittorrent、Prowlarr、TMDB、媒體庫路徑），與精靈共用同一批元件（Jellyseerr 的做法；Sonarr / Radarr / Prowlarr 的設定頁按領域分頁、每頁可增刪測）。TMDB 是自己的泊位，不與 Prowlarr 併成「來源」。原本「精靈跑完之後它就是設定入口」讓調整索引站要跳回靠泊流程的中間，字與流程都不對。

來源：brief §19 舊列「精靈改為每個服務手動選擇」「精靈的泊位與媒體庫」「只有 Berth 時的『套件內』卡片先查主機名」「既有服務不被改動」的判定規則那一半（原文在 `docs/archive/m2.md`、`docs/archive/m3.md`、`docs/archive/m4.md`）；查證在 `.scratch/m4/wizard-manual-choice-decision.md`。
