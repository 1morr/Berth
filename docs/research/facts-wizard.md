# 事實：設定精靈與既有服務

查證過的外部事實。編號沿用 brief 原本的節號（`§20.x`），程式碼與文件用它引用，編號不重用。索引在 [brief §20](../design-brief.md)。

## 事實

### 20.14 精靈手動選擇的慣例與既有服務的條件（2026-09-29 查證）

[ADR-0010](../adr/0010-wizard-manual-service-selection.md) 的依據，查證紀錄在 `.scratch/m4/wizard-manual-choice-decision.md`。慣例與各項實測的完整原文在 [`docs/research/wizard-existing-services.md`](wizard-existing-services.md)；三次實跑／查證另有自己的研究檔，下面只留結論。

- **Seerr 連媒體伺服器與加 Sonarr / Radarr 全程手動**：填位址與金鑰 → Test → Save，沒有自動偵測。【[Seerr：Media Server](https://docs.seerr.dev/using-seerr/settings/mediaserver)、[Seerr：Services](https://docs.seerr.dev/using-seerr/settings/services)】
- **Sonarr / Radarr 的 Download Client 也是手動**：Host、Port、Username、Password、Category，按 Test。【[Servarr Wiki：Sonarr System](https://wiki.servarr.com/sonarr/system)】
- **硬鏈接的前提是單一 `/data` 掛載**；分開掛或下載器在別台主機就要 Remote Path Mapping，而且硬鏈接失效。【[TRaSH Guides：Docker 目錄結構](https://trash-guides.info/File-and-Folder-Structure/How-to-set-up/Docker)、[TRaSH Guides：Sonarr Remote Path Mapping](https://trash-guides.info/Sonarr/Tips/Sonarr-remote-path-mapping)】Berth 不做 Remote Path Mapping（§18），所以既有服務必須與 Berth 同主機、同容器路徑（§16.4）。
- **qBittorrent 5.2 起有 API key**（`Authorization: Bearer <key>`）；Berth 這一輪只做 WebUI 帳密（版本下限 4.4 不變）。【[qbittorrent-api：Behavior & Configuration](https://qbittorrent-api.readthedocs.io/en/latest/behavior%26configuration.html)】
- **Prowlarr 的 API 只收 API key**（Settings → General → Security），帳密只給瀏覽器；既有 Prowlarr 要的是位址 + API key。【[Servarr Wiki：Prowlarr Settings](https://wiki.servarr.com/prowlarr/settings)】
- **容器裡的 `localhost` 是容器自己**：Docker Desktop 內建 `host.docker.internal`；Linux 要在 compose 加 `extra_hosts: ["host.docker.internal:host-gateway"]`，宿主上的服務要監聽 `0.0.0.0`（只聽 `127.0.0.1` 的連不到）。【[Nick Janetakis](https://nickjanetakis.com/blog/connect-to-a-service-running-on-your-docker-host-from-a-container)】
- **套件內那一台「已經設過介面登入」怎麼認**（M4 票 15，2026-09-29 查證＋實測）：
  - qBittorrent：`app/preferences` 讀得到 `web_ui_username`、**讀不到密碼**（`web_ui_password` 自 Web API 2.3.0 起 write-only）。全新的 linuxserver 那一台帳號是預設的 `admin`。所以**帳號不是 `admin` 就當設過了**；還是 `admin` 的一律當沒設過、要使用者設一組（寧可多問一次）。【[qBittorrent Wiki：WebUI API (4.1)](https://github.com/qbittorrent/qBittorrent/wiki/WebUI-API-(qBittorrent-4.1))】
  - Prowlarr：`GET /api/v1/config/host` 全新是 `authenticationMethod: "none"`、`username: ""`（2.6.5 實測）；設過是 `forms`（或 `basic`）加帳號。**方法不是 `none` 就當設過了**。
- **撞名撞 port 時 `docker compose up -d` 的行為**（M4 票 16 實測，2026-09-29；Docker Engine 29.6.2、Compose v5.3.1、Docker Desktop on WSL2；`scripts/experiments/compose_collisions.py`）：社群的說法「撞到的那一台起不來、其他照常起」**只對撞 port 成立**。
  - **撞名**：`up -d` 結束碼 1（`Conflict. The container name … is already in use`），**其他容器（連 `berth` 在內）都只建立、停在 `created`**。容器名改成 `berth-*` 之後同一個情境四個都起來。
  - **撞 port**：結束碼 1（`port is already allocated`），**只有那一台停在 `created`**，其餘照常 `running`。
  - `COMPOSE_PROFILES=`（空字串，三個都接既有）只起 `berth`。
- **從 `COMPOSE_PROFILES` 拿掉服務再 `up -d`，停不掉已經在跑的那一台**（M4 票 36，2026-10-06 實測；同上版本；`scripts/experiments/compose_profile_removal.py`）：Compose 不動不在啟用 profile 裡的服務（`--remove-orphans` 也一樣）；`docker compose stop <服務>` 才停得掉，之後再 `up -d` 留在 `exited`；不帶 `--profile '*'` 的 `down` 不收它們。所以「選了既有」的指示是兩步：改 `COMPOSE_PROFILES` ＋ `docker compose stop <服務>`。
- **`extra_hosts: host.docker.internal:host-gateway` 在 Docker Desktop 上不蓋掉內建的解析**（同一次實測）：容器照樣連得到宿主發佈的 port（回 200）；原生 Linux 的結果見下面 Unraid 那一條。
- **Unraid 實跑**（M4 票 55，2026-10-08；Unraid 7.1.4、Docker 27.5.1、Compose v2.40.3；全文在 [`docs/research/unraid-trial-2026-10-08.md`](unraid-trial-2026-10-08.md)）：官方 compose 原樣、只改 `.env`，S1 三個套件內走完並入庫一部；實跑的那一套 2026-10-09 已全部退回（研究檔 §8）。
  - **user share（shfs）上的硬鏈接成立**，前提是全域「Tunable (support Hard Links)」＝ Yes（`fuse_useino="yes"`）；入庫的兩個名字同 inode、links 2。**shfs 回報的 inode 是合成的**（高位是底下那顆碟的 `st_dev`），帳本記的 `(dev, inode)` 是這個合成值。
  - **cache → array 的 mover 保住硬鏈接**（links 2、同一個 inode；Jellyfin 照樣 stream、qBittorrent 照常做種、Berth 對帳 0 件）。**shfs 的 inode 跟著換碟而變**，帳本記的那一個從此過期：只有刪除時的「是不是 Berth 放的」在「來源已被使用者刪掉＋搬過碟」時認不出、把媒體庫那一份留著（研究檔 §6 U4）。mover 不搬正被開著的檔，做種中被讀的那一次留在 cache。【[TRaSH Guides：Unraid](https://trash-guides.info/File-and-Folder-Structure/How-to-set-up/Unraid)】
  - **`PUID=99`、`PGID=100` 照 `.env` 生效**（建出來的全是 `nobody:users`）。
  - **`host-gateway` 在原生 Linux 上成立**：`host.docker.internal` 解成 `172.17.0.1`（docker0），打得到宿主上既有的 qBittorrent 與 Emby。
  - **Compose Manager 的 stack 預設存在隨身碟**（`/boot/config/plugins/compose.manager/projects/<名字>/`）；它的 Indirect Path 讓 stack 指到別的目錄（讀外掛 2025.11.01 原始碼，沒有在 UI 上實按）。所以 README 叫人把部署目錄放 appdata、stack 名填 `berth`。
- **既有服務已經把別的資料夾掛在 `/data` 底下時再多掛一條 `DATA_ROOT:/data`**（M4 票 63，2026-10-14 實測；Docker Desktop 29.6.2 on Windows；`scripts/experiments/nested_data_mount.sh`；**沒有在 Unraid 上跑**，票 55 的 U6）：
  - 兩條並存，`-v` 的先後不影響：`/data` 是 `DATA_ROOT`，`/data/tvshows` 是原本那個資料夾，裡面的東西照舊看得到。
  - Docker 在 `DATA_ROOT` 裡建出同名的空資料夾當掛載點，跑完留著；`DATA_ROOT` 裡原本就有同名資料夾時被子掛載蓋住（宿主上不動）。Berth 只用 `/data/torrent` 與 `/data/library`，所以只有子掛載叫這兩個名字時才會蓋住 Berth 的目錄。
- **原生 Linux、rootless Docker 實跑**（M4 票 42，2026-10-09；Ubuntu 26.04 LTS、Docker 29.7.1 rootless、Compose v5.3.1；VM；全文在 [`docs/research/linux-trial-2026-10-09.md`](linux-trial-2026-10-09.md)）：v0.2.0 的 zip 照英文 README 部署，S1 精靈頁 1–6 走完、送單成功；S2 頁 3 兩條各 6/6。**沒有入庫**（下載 40 分鐘只到 19.8%，原因沒查清）；入庫的端到端由 Unraid（票 55）與 Docker Desktop（票 58）實證。
  - **rootless 的 `PUID` / `PGID` 要填 `0` / `0`**：填 `id -u` 時整套照常，但 `DATA_ROOT` 與 `CONFIG_ROOT/*` 在宿主上全是 subuid（100999），宿主帳號寫不進、刪不掉。linuxserver 官方不支援 rootless（[論壇回覆](https://discourse.linuxserver.io/t/setting-puid-and-pgid-to-root/3726)），`0` / `0` 在 jellyfin 12.1、qbittorrent 5.2.4、prowlarr 2.6.5 上實測可用。
  - **PUID / PGID 與 `DATA_ROOT` 擁有者不一致時**：頁 3 三條 Route 都停在第一項 `category` 的 `berth_cannot_write`（`Permission denied: '/data/torrent'`），文案點名 `.env` 的 PUID / PGID；票 72 起多說一句 rootless 不要 chown、改填 `PUID=0`、`PGID=0`。
  - **rootless 上 `host.docker.internal` 連不到宿主**：`host-gateway` 解成 `172.17.0.1`，但那是 RootlessKit 網路命名空間裡的 docker0；宿主的區網 IP 都通（只聽 `127.0.0.1` 的除外）。rootless 上既有服務填區網 IP（M4 票 72）。
  - **qBittorrent 的免密白名單在 rootless 上仍安全**：白名單只有 Berth 的 `172.28.0.2/32`；從宿主與區網不登入打 API 都是 403。【[Docker：Rootless mode › Troubleshooting](https://docs.docker.com/engine/security/rootless/troubleshoot/)】
  - Prowlarr 拿不到 `indexers.prowlarr.com` 的站定義時只剩磁碟上的 5 個，推薦清單上的站一個都不在，頁 4 的主鍵跟著消失（M4 票 73 起說出原因與下一步）。**網路通了之後不必重啟 Prowlarr**（2026-10-14 讀 Prowlarr develop 原始碼，未實跑）：每次讀 `indexer/schema` 都先向 `https://indexers.prowlarr.com/master/12` 拿清單、失敗才讀磁碟，所以 Berth 的「重新讀取」就拿得到。Prowlarr 的介面是 BrowserRouter、不走 `#/`。**2026-10-14 對 linuxserver 2.6.5 實開**（M4 票 102）：`/#/settings/general` 與 `/#/indexers` 都落在首頁，`/settings/general` 是「General Settings - Prowlarr」，`/indexers` 是找不到頁；索引站清單就是首頁 `/`。前端連到 Prowlarr 的那幾頁收在 `web/src/setup/serviceWeb.ts` 的 `PROWLARR_PAGE`。【[原文](linux-trial-2026-10-09.md#從-brief-搬來2014)；[AppRoutes.tsx](https://github.com/Prowlarr/Prowlarr/blob/develop/frontend/src/App/AppRoutes.tsx)】
- **Prowlarr 的版本下限是 1.3.2**（M4 票 17，2026-09-29 查證；全表與來源在 [`docs/research/prowlarr-version-floor.md`](prowlarr-version-floor.md)，讀各 tag 原始碼，沒有對 1.3.x 實跑）：
  - 卡住下限的只有匿名的 `GET /ping`（[`5abb5ad`](https://github.com/Prowlarr/Prowlarr/commit/5abb5ada4991142e871dcfa94c32c8e4cb0ea247)），第一個 stable 是 **1.3.2.3006**（2023-04-07）；其餘端點與欄位從第一個 tag 0.1.0.361（2021-06）就有。`passwordConfirmation` 要到 1.10.5.4116 才有，但不推高下限（舊版 JSON 設定不拒收多的欄位，未實跑）。
  - 版本從 **`GET /api/v1/system/status` 的 `version`** 讀，四段（`2.6.5.5623`）；它**要 API key**（不帶是 401），所以順便驗了 key。
  - **比下限舊的那一台也讀得到版本**（M4 票 20，2026-09-30 對 1.0.1.2220 實測）：`GET /ping` 回 **200 `text/html`**（所以先問它只會得到「不是 JSON」），`system/status` 帶 `X-Api-Key` 回 200、不帶或錯的 key 是 **401**。Berth 的連線測試因此從 `system/status` 問起、不問 `/ping`。
  - **介面登入在現行版本是必填**（M4 票 20，讀 v2.6.5.5623 原始碼）：第一次打開介面就是一個關不掉、要人設登入的視窗（`AuthenticationRequiredModal`）。精靈因此把套件內那一台的介面登入寫成必填。【[原文](prowlarr-version-floor.md#從-brief-搬來2014)】
  - 目前最新 stable 是 2.6.5.5623（2026-09-16）。2.6.3 起多了 Allowed Hosts：使用者自己設了清單時，Berth 用別的主機名連可能被擋，回什麼沒查。
- **位址的協定寫錯時三個服務的樣子**（M4 票 25，2026-10-01 實測；berth image 的 Python 3.13 + OpenSSL 3.5.7、httpx 0.28.1）：
  - **Jellyfin 12.1、Prowlarr 2.6.5** 對 TLS 的 ClientHello 回 HTTP 400：`ssl.SSLError` 理由 `WRONG_VERSION_NUMBER`（httpx 包成 `ConnectError`）。**qBittorrent 5.2.3** 不回、等 HTTP 請求：握手一直等到連線逾時（`ConnectTimeout`，鏈上是 `ssl.SSLWantReadError`）。
  - 反方向（`http://` 打到講 https 的 port）只做了本機的 Python `ssl` 伺服器：它重設連線（`ReadError` / `ConnectionResetError`），與別的斷線分不開，Berth 不認它。
  - **位址沒寫協定**（`nas:8080`、`localhost:8096`…）：httpx 連都不連就丟 `UnsupportedProtocol`（`nas:8080` 被讀成協定 `nas`）。
- **停掉的 compose 容器，主機名解不到**（同一天實測）：Docker 的內建 DNS 只解析在跑的容器，連線測試是 `socket.gaierror`。所以套件內「主機名解不到」的補法要同時說容器停了與不在 compose 裡。
- **解不到要多久**（M4 票 30，2026-10-03 實測，Docker Desktop 29.6.2，從 `berth` 容器裡 `socket.getaddrinfo`）：三個名字都是 `gaierror -5`（`EAI_NODATA`），各約 1.27 秒，三個並行問的 `GET /setup/compose` 約 2.6 秒；都起來之後 8 毫秒內回。宿主上的行為不同、不能拿來推（Windows 開發機要 7 秒，代理工具的 fake-IP DNS 連 `.invalid` 都答一個 198.18.x）。`adapters.dns` 因此以 10 秒為上限、逾時當作解得到（說不出結論就不說「沒在跑」）。
