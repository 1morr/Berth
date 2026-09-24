# 06b — 部署：五個對外 port 進 `.env`，深連結與內建 qBittorrent 位址跟著走

**Status:** ready-for-agent

**Blocked by:** None — can start immediately（只動 `deploy/`、`config.py`、`deeplink.py`、`clients.py`，與 01–06 不衝突）

**讀:** plan §9.1、§9.2（qBittorrent 的發佈 port 那一條）、§1.1（`config.py`）；brief §12（深連結）、§16.3、§19（2026-09-24「部署的 port 進 `.env`」）、§20.7；`berth/services/deeplink.py` 的 docstring

## 做什麼

使用者試跑時，套件的預設 port 與開發環境撞在一起：8383 / 8080 / 8096 被開發中的 dev server 與 e2e 佔著，只能手改 compose 檔。改成 `18096:8096` 之後，Jellyfin 的深連結還是開到 `localhost:8096`，也就是開發用的那一台。原因是 `deeplink.py` 推導的第 3 條用的是**容器內**的 port。改成 `18080:8080` 之後，qBittorrent 的 WebUI 直接回 401，因為 Host 檢查連 port 都比對（plan §9.2）。

**決定**（使用者 2026-09-24 拍板，brief §19）：**只有 Berth 在容器裡看不到的主機端事實進 `.env`，也就是五個對外 port。** 其餘設定（服務位址與憑證、下載目錄與媒體庫根、Route、對外網址、磁碟門檻）維持在精靈與設定頁。理由記在 brief §19：同一個值有兩個來源時必須選邊，Immich 選擇鎖 UI，Servarr 只開少數幾個 key 給環境變數；Route 是動態的；`.env` 不放秘密。

| `.env` 變數 | 預設 | compose |
| --- | --- | --- |
| `BERTH_PORT` | 8383 | `${BERTH_PORT}:8383` |
| `JELLYFIN_PORT` | 8096 | `${JELLYFIN_PORT}:8096`；**同一個值傳給 `berth`**，作為深連結推導第 3 條的 port |
| `QBITTORRENT_WEBUI_PORT` | 8080 | **內外兩側都用它**（`${…}:${…}`），並設 linuxserver 的 `WEBUI_PORT`；healthcheck 跟著改；**同一個值傳給 `berth`**，套件內 qBittorrent 的位址由 `http://qbittorrent:8080` 改成讀它 |
| `QBITTORRENT_BT_PORT` | 6881 | 內外兩側都用它（TCP 與 UDP），並設 `TORRENTING_PORT`：對外公告的 port 要與實際連得進來的一致 |
| `PROWLARR_PORT` | 9696 | `${PROWLARR_PORT}:9696` |

- **Berth 那一端**：`config.py` 多兩個欄位，一律可省略，省略時就是現在的 8096 與 8080。
  - `deeplink.jellyfin_web` 的第 3 條改用 Jellyfin 的對外 port，**不再從 `base_url` 取 port**。
  - `clients.BUNDLED_QBITTORRENT_URL` 從常數改成由設定組出。精靈的偵測（`setup._probe`）、`qbittorrent.py`、`routes.py` 三個消費點都改讀它，偵測才認得出換過 port 的套件內 qBittorrent 是 `bundled`。
  - 環境變數的名稱照 `config.py` 既有的慣例取，寫進 README 的環境變數表。
- **不預置 `WebUI\HostHeaderValidation=false`**：它是 qBittorrent 防 DNS rebinding 的那一道，寫進 preseed 等於替每個使用者關掉它。401 的原因是 port 內外不一致，內外兩側一起換之後 Host 檢查本來就過得了（plan §9.2）。
- **`.env.example`**：五個變數加上註解，說明什麼時候要改（port 撞到），以及 qBittorrent 的兩個 port 為什麼內外兩側一起換。
- **README**：compose 的 port 表改成列出變數；「疑難排解」裡 `18080:8080` 吃 401 那一段，改寫成「改 `QBITTORRENT_WEBUI_PORT`，不要手改 compose 檔」。
- **plan §9.1 / §9.2**：port 欄與「qBittorrent 的發佈 port 不可以改號碼」那一條，改寫成現在的做法。
- **e2e 不動**：`tests/e2e/harness.py` 寫死預設 port，這一套本來就用預設值。

## 驗收

- [ ] 五個變數在 `.env.example`，compose 都用到；`JELLYFIN_PORT` 與 `QBITTORRENT_WEBUI_PORT` 同時傳給 `berth`。由一條讀 compose 與 `.env.example` 的測試守住，**測試檔內做雙向變異**：拿掉 `berth` 的那一個環境變數、或 qBittorrent 只改一側時會紅；改變數註解或 YAML 排版不紅
- [ ] 深連結：套件內 Jellyfin、設定了對外 port、沒填對外網址時，回的 port 是對外 port；沒設時仍是 8096（單元測試，紅 → 綠）
- [ ] 套件內 qBittorrent 的位址由設定組出；換 port 後精靈的偵測仍判成 `bundled`（整合測試）
- [ ] 實跑一次非預設 port 的整套（例如 18383 / 18096 / 18080 / 16881 / 19696，與預設那一套同機並存）：精靈走完且 qBittorrent 判成套件內；瀏覽器開 `localhost:18080` 不是 401，**不靠** `HostHeaderValidation=false`；媒體庫的「在 Jellyfin 開啟」開到 18096。貼結果
- [ ] README、`.env.example`、plan §9.1 / §9.2、CHANGELOG 同步
- [ ] lint、type、test 綠燈

## Comments

- 觸發這張票的試跑環境在 `C:\Users\Roxy\berth-trial\`（repo 外），它的 qBittorrent 目前靠手動加的 `WebUI\HostHeaderValidation=false` 才打得開 18080，違反 plan §9.2。這張票做完後，改用新的 compose 與 `.env` 重起，並拿掉那一行。
- 2026-09-24 補：那一行也寫進了試跑目錄的 preseed 副本（`C:\Users\Roxy\berth-trial\preseed\qbittorrent\10-berth.sh` 的 `KEYS`），重置環境時會自動加回去。驗收「不靠 `HostHeaderValidation=false`」那一條要連這一份一起拿掉，或直接改用 repo 的 `deploy/preseed/`。
