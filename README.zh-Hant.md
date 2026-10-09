# Berth

[English](README.md) · **繁體中文**

自架的媒體取得工具，終點是你的 Jellyfin 媒體庫。

## 為什麼做 Berth

Seerr 搭配 Sonarr、Radarr 要設定好幾個服務，而且發佈由它替你挑，拿到的不一定是你要的版本。Berth 讓你自己挑
發佈，來源可以是 Prowlarr 的搜尋結果，或 RSS（例如追當季動畫用的 Mikan），再由 Berth 匯入 Jellyfin。

## 能做什麼

- 在作品頁搜尋 Prowlarr，發佈由你自己挑。
- 訂閱 Mikan、Nyaa、acg.rip 的 RSS：新的一集自動送出並入庫。
- 對照 TMDB 認出每個檔案是哪部電影、哪一集，以 Jellyfin 認得的名字硬鏈接進媒體庫，不佔兩份空間。
- 替放進去的每個檔案記帳；每晚的檢查找出被刪掉的集數、被複製檔取代的硬鏈接、
  沒人認領的 torrent，列出每一件能怎麼處理。
- 在健康頁每 5 分鐘重新檢查服務與媒體庫路徑。
- 用精靈帶你設定：設好套件內的 Jellyfin、qBittorrent、Prowlarr，或接你已經在跑的，
  並用一個真的檔案證明硬鏈接成立。
- 介面可用繁體中文或英文。

| | |
| --- | --- |
| ![設定精靈正在檢查媒體庫路徑](docs/assets/screenshots/wizard.png) | ![在作品頁搜尋發佈](docs/assets/screenshots/title-search.png) |
| ![在 Berth 裡瀏覽 Jellyfin 媒體庫](docs/assets/screenshots/library.png) | ![健康頁](docs/assets/screenshots/health.png) |

Berth 是公開 beta。依賴它之前先讀〈[現況與已知限制](#現況與已知限制)〉。

## 需要什麼

- Docker Engine 或 Docker Desktop，加 Compose 2.23.1 以上（`docker compose version`；`docker compose`，不是
  `docker-compose`）。
- 一個放下載與媒體的資料夾，在一顆支援硬鏈接的本機磁碟上：不是 exFAT、不是網路磁碟。
  細節見 [Requirements](docs/guide/requirements.md)（英文）。
- **一把免費的 TMDB API key，先申請**，約五分鐘：
  1. 在 <https://www.themoviedb.org/signup> 註冊並收驗證信。
  2. 開 <https://www.themoviedb.org/settings/api> 申請 API key，用途選 **Personal / Education**。
     即時核發。
  3. 留下 **API Key** 或 **API Read Access Token** 其中一個；兩種 Berth 都收。

## 安裝

1. 建一個放 Berth 的資料夾，放進兩個檔：[`docker-compose.yml`](https://raw.githubusercontent.com/1morr/Berth/v0.2.1/deploy/docker-compose.yml)，以及存成 `.env` 的
   [`.env.example`](https://raw.githubusercontent.com/1morr/Berth/v0.2.1/deploy/.env.example)。旁邊不用放別的東西。兩個連結都是這一版的檔案，compose 才不會比
   image 新。Unraid 改成把這兩份貼進 Compose Manager：見 [Unraid](docs/guide/requirements.md#unraid)（英文）。

   ```bash
   mkdir berth && cd berth
   curl -fsSLo docker-compose.yml https://raw.githubusercontent.com/1morr/Berth/v0.2.1/deploy/docker-compose.yml
   curl -fsSLo .env https://raw.githubusercontent.com/1morr/Berth/v0.2.1/deploy/.env.example
   ```

2. 改 `.env`：
   - `DATA_ROOT`：下載與媒體庫放在哪；`CONFIG_ROOT`：四個服務的設定放在哪。預設的 `./data`、`./config` 試跑可以
     不改；正式用請給你媒體磁碟上的絕對路徑（`/srv/berth/data`、`C:\Berth\data`）。Unraid 上一定要是絕對路徑。
   - `PUID` / `PGID`：擁有 `DATA_ROOT` 的帳號（`id -u` / `id -g`；Unraid 是 `99` / `100`；
     [rootless Docker](docs/guide/requirements.md#rootless-docker) 是 `0` / `0`）。Windows 的 Docker Desktop 維持預設。
   - `TZ`：你的時區，例如 `Asia/Taipei`。
   - 已經在跑 Jellyfin、qBittorrent 或 Prowlarr？要接你原本那一台，就把它從 `COMPOSE_PROFILES` 拿掉；要兩台並存，
     就改它的 `*_PORT`。否則 `up -d` 會停在 `port is already allocated`。見
     [Connecting services you already run](docs/guide/existing-services.md)（英文）。

3. 啟動，等 `berth` 顯示 `(healthy)`（第一次拉 image 約一分鐘）：

   ```bash
   docker compose up -d
   docker compose ps
   ```

4. 開 <http://localhost:8383>，照精靈走。

## 設定精靈

六頁。Jellyfin、qBittorrent、Prowlarr 三頁先選「**套件內**」（這份 compose 起的那一台）或「**既有**」（你自己
已經在跑的）；每個選擇 Berth 都當場測給你看。

1. **Jellyfin**：建立 Jellyfin 管理員，或以管理員登入。這個帳號也是你登入 Berth 的帳號。
2. **qBittorrent**：設它的 WebUI 登入，或填你原本那一台的位址與帳密。
3. **媒體庫路徑**：每個媒體庫各一條 *Route*（從下載到媒體庫的路），Berth 用一個真的檔案證明硬鏈接成立。
   套件內的 Jellyfin 預設建 Movies、TV、Anime；接你自己的，就勾選 Berth 可以寫進哪幾個媒體庫。
4. **Prowlarr**：按一次加入推薦的公開索引站，或用你自己的。可以先跳過。
5. **TMDB**：貼上你的 key，要通過測試。
6. **完成**：說出跳過了什麼、去哪裡補。

逐頁細節，以及 Berth 在每個服務裡改了什麼：[Setup wizard](docs/guide/setup-wizard.md)（英文）。
備份 `${CONFIG_ROOT}/berth`（預設 `./config/berth`）：Berth 知道的一切都在那個資料夾。

## 現況與已知限制

Berth 是**公開 beta**。

- 只支援 **Jellyfin 12.0 以上**與 **Prowlarr**。不支援 Emby、Plex、Jackett。
- 還沒有通知：要打開 Berth 才看得到哪裡需要你。
- 完整實跑過的是 **Windows 的 Docker Desktop** 與 **Unraid 7.1**。**Ubuntu 26.04 的 rootless Docker** 上走完過精靈、
  送單也成功，但還沒在那裡入庫過（[實跑紀錄](docs/research/linux-trial-2026-10-09.md)）。其他 Linux
  發行版與 NAS 還沒實測。
- **不要把 Berth 直接開到公網。** 從區網或 VPN 連。
- 已知問題（追蹤票，中文）：
  - 沒有 Prowlarr（精靈裡跳過、或之後移除）時健康頁一直紅；還沒有「不用 Prowlarr」的選項
    （[61](.scratch/m4/issues/61-prowlarr-optional.md)）。
  - 新入庫的檔案沒出現時，Berth 請 Jellyfin 掃描全部媒體庫、不只它自己的；空媒體庫的第一次入庫可能要十分鐘以上
    才顯示「Jellyfin 已收錄」（[62](.scratch/m4/issues/62-jellyfin-scan-scope.md)）。
  - 既有服務少了 `/data` 掛載時，畫面給的補法寫 `${DATA_ROOT}:/data` 而不是你真正的資料夾；Jellyfin 的掛載
    要到頁 3 才檢查（[63](.scratch/m4/issues/63-copyable-mount-remedies.md)）。
  - 既有 Jellyfin 要先有你要的每一種類型的媒體庫；Berth 只替它加路徑、不新建
    （[64](.scratch/m4/issues/64-new-library-on-existing-jellyfin.md)）。
  - 換到另一台 qBittorrent 之後，舊那台上還在做種的 torrent 留在那裡、不再被追蹤，Berth 也不會說
    （[65](.scratch/m4/issues/65-switch-explains-what-stays.md)）。
- 上一輪審計之後已修好：
  - 換 qBittorrent 之後 Berth 自己重新檢查每一條 Route，健康頁不再把沒檢查過的 Route 算成綠燈
    （[59](.scratch/m4/issues/59-health-tells-the-truth-after-switch.md)）。
  - 重裝或資料庫遺失之後，精靈最後一頁與「待處理」頁會給「從媒體庫重建帳本」
    （[60](.scratch/m4/issues/60-rebuild-ledger-from-the-ui.md)）。

## 指南

- [Setup wizard](docs/guide/setup-wizard.md)：逐頁細節、帳號與密碼、精靈之後的各頁。
- [Connecting services you already run](docs/guide/existing-services.md)：`/data` 掛載（Compose、
  `docker run`、Unraid 模板）、`COMPOSE_PROFILES`、換一台。
- [Requirements](docs/guide/requirements.md)：硬鏈接、Linux / Windows / Unraid、各服務的版本下限。
- [Upgrading](docs/guide/upgrading.md)：image tag、升級步驟、自己 build image。
- [Troubleshooting](docs/guide/troubleshooting.md)：port、`Unauthorized`、`host.docker.internal`。
- [Backup, secrets and reinstalling](docs/guide/backup-and-reinstall.md)：Berth 存了什麼、從頭再來、重建帳本。
- [CHANGELOG](CHANGELOG.md)：每一版改了什麼。
- [開發](docs/development.md)：建置、測試與目錄結構。

## 授權與歸屬

MIT，見 [LICENSE](LICENSE)。

<img src="docs/assets/tmdb.svg" alt="TMDB" height="28">

This product uses the TMDB API but is not endorsed or certified by TMDB.
（本產品使用 TMDB 的 API，但未經 TMDB 認可或認證。TMDB 的條款限非商業使用。）
