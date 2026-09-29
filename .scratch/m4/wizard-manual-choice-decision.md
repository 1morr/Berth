# 精靈改為每個服務手動選擇（2026-09-29，使用者拍板）

使用者試跑全新環境後提出：Jellyfin、qBittorrent、Prowlarr 各一頁，進頁後由使用者手動選「套件內」或「既有」，
不再偵測是否套件內；既有就填連線資訊，套件內就建立帳號或沿用 Jellyfin 的。compose 裡用不到的服務可以拿掉，
忘了拿掉也不致命。協調者查證後整理如下，四個待決事項已由使用者拍板（見最後一節）。

## 慣例來源

- **Seerr**：連 Jellyfin 與加 Sonarr / Radarr 全程手動填 URL + 金鑰 → Test → Save，沒有自動偵測。
  https://docs.seerr.dev/using-seerr/settings/mediaserver 、https://docs.seerr.dev/using-seerr/settings/services
- **Sonarr / Radarr 的 Download Client**：Host、Port、Username、Password、Category，手動填、按 Test。
  https://wiki.servarr.com/sonarr/system
- **TRaSH Guides**：下載器與媒體庫共用同一個 `/data` 掛載，硬鏈接與 atomic move 才成立；分開掛或下載器在別台主機就
  要 Remote Path Mapping，且硬鏈接失效。https://trash-guides.info/File-and-Folder-Structure/How-to-set-up/Docker 、
  https://trash-guides.info/Sonarr/Tips/Sonarr-remote-path-mapping

## 設計

### 頁面與順序（取代 plan §9.3 現行的 8 步）

1. **Jellyfin**（擁有者）：先選套件內 / 既有 → 套件內建立管理員、既有用管理員登入 → 這個人成為擁有者 → Berth 自己
   建 API key「Berth」（使用者不必手動貼 key，比 Seerr 省一步）。
2. **qBittorrent**：選套件內 / 既有 → 套件內設定 WebUI 登入（預設「沿用 Jellyfin 帳密」）、既有填 URL + WebUI 帳密 → 測試。
3. **Prowlarr ＋ 索引站**（併成一頁）：選套件內 / 既有 → 套件內從掛載的 config.xml 讀 API key（零輸入）並設介面登入
   （同樣可沿用 Jellyfin 帳密）、既有貼 API key → 挑索引站（票 09 的「先測試再加入」）。既有 Prowlarr 用使用者已有的
   索引站，Berth 不替它加站（票 05 已擋 422）。
4. **媒體庫與路徑**：Jellyfin 媒體庫、Route、按鈕觸發的檢查（票 08）。需要 Jellyfin 與 qBittorrent 都已接好。
5. **TMDB**。
6. **完成**。

拿掉現行第 2 步「偵測」。Berth 沒有自己的帳號頁（brief §11）；它自己的設定就是 3–5 頁。

### 規則

- **不偵測、不判定，但選完要驗證**：選了「套件內」而 compose 裡沒啟動那個服務（`COMPOSE_PROFILES` 拿掉了）時，測試
  失敗要說出怎麼補：「把 `qbittorrent` 加回 `.env` 的 `COMPOSE_PROFILES` 再 `docker compose up -d`」。選擇存下來，
  「套件內 / 既有」從此由選擇決定，取代 `services/setup.py` 的 `_verdict_*` 判定（票 05 的「既有服務不寫登入、不改
  全域偏好」保留，改讀使用者的選擇）。
- **套件內但已初始化過**（重裝保留 config、精靈中途中斷）：Jellyfin 已有管理員就改成「用管理員登入」，不再建立；
  qBittorrent / Prowlarr 已設過登入同理。
- **既有服務要給的東西各不相同**：
  - Jellyfin：URL + **管理員**帳密（非管理員拒絕，票 06）。版本下限 **12.0 維持**（brief 既有決定）。
  - qBittorrent：URL + WebUI 帳密；只建 Berth 自己的分類，不改全域偏好（票 05）。版本下限 4.4（Web API 2.8.4）。
    qBittorrent 5.2 起有 API key（`Authorization: Bearer`），之後可當第二種接法，這一輪不做。
    https://qbittorrent-api.readthedocs.io/en/latest/behavior%26configuration.html
  - Prowlarr：URL + **API key**（Settings → General → Security）。Prowlarr 的 API 只收 API key，帳密只給瀏覽器登入。
    https://wiki.servarr.com/prowlarr/settings 。版本下限目前沒有決定，要補查並寫進 brief §20。
- **「沿用 Jellyfin 帳密」**：套件內 qBittorrent / Prowlarr 的登入預設勾選。勾選時帳號帶入擁有者名字、密碼請使用者
  **打一次**，Berth 先向 Jellyfin 驗證這組帳密正確再寫入（Berth 仍不存 Jellyfin 密碼，票 06）；取消勾選就照票 07
  自設一組、打兩次。
- **既有服務的共同條件（使用者沒提到、最關鍵）**：Berth 用硬鏈接入庫，所以既有的 qBittorrent 與 Jellyfin 必須與
  Berth **在同一台主機、把同一個父目錄掛在同一個容器路徑（`/data`）**。**不做 Remote Path Mapping**（brief §18 既有
  決定，使用者 2026-09-29 再確認）。既有服務在另一台 NAS、或掛成 `/downloads`、`/tv` 分開的，不支援。「既有」選項旁
  說明這個條件；媒體庫與路徑頁的探測檔 / 硬鏈接檢查失敗時，說明要改成「怎麼改掛載」。
- **容器裡的 localhost**：使用者填 `localhost` / `127.0.0.1` 時提示：Berth 在容器裡，要填 `host.docker.internal`
  （Docker Desktop 內建；Linux 需要 compose 的 `extra_hosts: ["host.docker.internal:host-gateway"]`，且服務要監聽
  0.0.0.0 而不是 127.0.0.1）或區網 IP。https://nickjanetakis.com/blog/connect-to-a-service-running-on-your-docker-host-from-a-container
- **compose 裡沒拿掉的套件內服務**：同一台主機上的既有容器大多就叫 `jellyfin` / `qbittorrent` / `prowlarr`、用
  8096 / 8080 / 9696 / 6881，與套件撞名撞 port，那個套件內容器會起不來（社群報告其他容器照常起，**要自己實測**）。
  所以：套件的 `container_name` 改成 `berth-jellyfin` / `berth-qbittorrent` / `berth-prowlarr`（`berth` 維持）；選
  「既有」時頁面說出要從 `.env` 的 `COMPOSE_PROFILES` 拿掉哪一個（不叫人改 compose 檔）。

## 對已做與未做的票

| 票 | 處理 |
|---|---|
| 05（done） | 保護保留，判定依據改成使用者的選擇；`_verdict_*` 與偵測判定整段刪除（在新票 A 做） |
| 06（done） | 擁有者流程保留成 Jellyfin 頁；拿掉擁有者前的偵測；頁首加二選一；補「套件內但已初始化 → 登入」（新票 A） |
| 07（done） | 登入欄位保留；加「沿用 Jellyfin 帳密」（新票 A） |
| 08（未做） | 內容照舊有效（按鈕觸發、每條 Route 一列、slug 去空白），Blocked by 新票 A；失敗說明加「改掛載」 |
| 09（未做） | 內容照舊有效，改成在 Prowlarr 頁裡，Blocked by 新票 A |
| 新票 A | 精靈改為手動選擇：每個服務一頁、二選一、拿掉偵測步驟、選擇存下來、選完要測試、沿用 Jellyfin 帳密、套件內已初始化改登入 |
| 新票 B | compose：`container_name` 加 `berth-` 前綴（真服務 e2e harness、berth-lab 同步）、berth 服務加 `extra_hosts` host-gateway；`.env.example` 寫明接既有時拿掉哪個 profile；實測撞 port / 撞名時 `docker compose up -d` 的行為並記進 brief §20 |
| 新票 C | 既有服務防呆：`localhost` / `127.0.0.1` 提示、各服務版本門檻的說明文案、查證 Prowlarr 版本下限寫進 brief §20 |

建議順序：A → B → C → 08 → 09（B、C 不依賴 A）。

## 使用者拍板（2026-09-29）

1. Jellyfin 版本下限**維持 12.0**（「還在開發中，開發完可能多人都用 12 了」）。
2. **不做 Remote Path Mapping**，把條件講清楚。
3. 套件容器名**改成 `berth-*` 前綴**。
4. **Prowlarr 與索引站併成一頁**；**「沿用 Jellyfin 帳密」預設勾選**。

## 寫進文件時再拍板（2026-09-29，子 session）

1. **泊位順序維持 M3 票 06d**：Jellyfin → qBittorrent → 媒體庫與路徑 → Prowlarr ＋ 索引站 → TMDB → 完成（上面〈頁面與順序〉
   把媒體庫與路徑排在 Prowlarr 之後，改掉）。
2. **Berth 寫進套件內 qBittorrent / Prowlarr 的介面密碼只存加鹽雜湊**：勾了「沿用 Jellyfin 帳密」時那就是 Jellyfin 的密碼，
   照票 07 存明文會推翻票 06「資料庫裡沒有擁有者的明文密碼」。

新票 A、B、C 分別是 `.scratch/m4/issues/15-wizard-manual-choice.md`、`16-compose-names-host-gateway.md`、
`17-existing-service-guards.md`。
