# Berth 在原生 Linux（rootless Docker）上實跑（2026-10-09，M4 票 42）

範圍：v0.2.0 的 release zip 與 `ghcr.io/1morr/berth:latest`（0.2.0），照英文 README 部署到使用者電腦上 VMware
Workstation 的 Ubuntu VM（brief §19 E8）。只在 `~/berth-trial-42/`、`/home/cppt/berth-data*`、`/home/cppt/berth-s2-data`
與這張票起的容器（`berth`、`berth-*`、`s2-*`）上寫；票 70 同時在同一台 VM 上跑的 `berth-t70` 沒碰。截圖與指令輸出在
[`linux-trial-2026-10-09/`](linux-trial-2026-10-09/)。Unraid（rootful）的那一輪見 [`unraid-trial-2026-10-08.md`](unraid-trial-2026-10-08.md)。

## 1. 結論先講

- **這台是 rootless Docker**（context `rootless`、slirp4netns、`--disable-host-loopback`、builtin port driver），使用者
  不能免密 sudo。rootless 讓 README 的兩個說法在這裡不成立，是這一輪最主要的發現：
  - **`PUID` / `PGID` 照 README 填 `id -u` / `id -g`（1000）會讓宿主上的自己寫不進 `DATA_ROOT`**：容器裡的 uid 1000
    對到宿主的 subuid 100999。整套照常運作（Route 6/6，硬鏈接兩端同一個擁有者），但 `DATA_ROOT` 與 `config/*`
    在宿主上全是 `100999:100999`，cppt 連 `touch` 都不行（§4.1）。**rootless 要填 `PUID=0`、`PGID=0`**：容器裡的
    root 就是跑 dockerd 的那個帳號，Berth 與三個 linuxserver image 寫出來的全是 `cppt:cppt`（§4.3、S2 全程）。
  - **`host.docker.internal` 連不到宿主上的任何服務**：它照樣解成 `172.17.0.1`，但那是 RootlessKit 網路命名空間裡的
    docker0，不是宿主。宿主上的原生服務、其他 rootless 容器發佈的 port 都是 connection refused；**改填宿主的區網 IP
    就通**（只監聽 `127.0.0.1` 的仍然連不到）。§5。
- **S2（既有 Jellyfin 與既有 qBittorrent，各自只多掛一條 `/data`）走到頁 3，兩條 Route 各 6/6**：位址用
  `http://192.168.50.99:<port>`。`host.docker.internal` 那一條的驗收在 rootless 上答案是「連不到」，票上那一格留給使用者決定；
  rootful 原生 Linux 的 `host-gateway` 只有 Unraid 上的 `getent` 與 curl（票 55），沒有用它走過 S2。
- **PUID / PGID 與 `DATA_ROOT` 擁有者不一致時，頁 3 的錯誤訊息看過了**：`berth_cannot_write`，「Berth itself cannot
  write to /data/torrent …」（§4.2）。訊息指對了地方，但補法「在宿主上 chown 給那組 PUID / PGID」在 rootless 上做不到
  （要 chown 成 100999，沒有 sudo），rootless 的補法是 `PUID=0`。
- **S1 沒有入庫**：精靈頁 1–3 照 README 走完（三條 Route 各 6/6），但這台 VM 自己的 Clash Verge（mihomo TUN）選的
  節點整段時間都不通，TMDB、索引站、`lscr.io`、Prowlarr 的站定義全部 TLS 失敗（§6）。頁 4 加不了站、頁 5 測不了
  TMDB，所以沒有走到送單與入庫。這是這台機器的網路，不是 Berth；改代理設定是使用者的事，這一輪沒有動。
- **qBittorrent 的免密白名單在 rootless 上仍然安全**：rootless 的 `-p` 不保留來源位址，但白名單只有 Berth 的
  `172.28.0.2/32`，從宿主與區網不登入打 API 都是 403（§5.2）。
- **改的是文件**：README（兩份）、`docs/guide/requirements.md`〈Linux〉、`docs/guide/existing-services.md`、部署檔
  `.env.example` 與 compose 的註解。精靈文案（兩處說 `host.docker.internal`／chown 的補法）開票 72；頁 4 推薦站全部
  不在 Prowlarr 時畫面不說原因，開票 73。

## 2. 環境

完整輸出：[`environment.txt`](linux-trial-2026-10-09/environment.txt)。

| 項目 | 值 |
| --- | --- |
| 主機 | VMware Workstation 上的 VM `ubuntu-devbox`（主機名 `cppt-dev`，橋接網路 192.168.50.99） |
| 系統 | Ubuntu 26.04 LTS，kernel 7.0.0-38-generic |
| Docker / Compose | 29.7.1 **rootless**（`docker context show` → `rootless`；`SecurityOptions` 含 `name=rootless`）／ Compose v5.3.1 |
| RootlessKit | `--net=slirp4netns --disable-host-loopback --port-driver=builtin`（`dockerd-rootless.sh` 的預設） |
| 帳號 | `cppt`（uid 1000，在 `sudo` 群組但 sudo 要密碼：`sudo -n true` → `interactive authentication is required`）；`/etc/subuid` `cppt:100000:65536` |
| 檔案系統 | `/`（含 `/home/cppt`）ext4，98G |
| 網路 | Clash Verge（`verge-mihomo`，TUN、fake-ip `198.18.0.0/30`、rule 模式）；GitHub 走 DIRECT，其餘走一個這段時間不通的節點（§6） |
| image | `ghcr.io/1morr/berth:latest` `sha256:9ec2722c…12eb`（`/api/health` 回 `0.2.0`）；`lscr.io/linuxserver/jellyfin:version-12.1ubu2604`（12.1.0）、`qbittorrent:latest`（5.2.4）、`prowlarr:latest`（2.6.5） |

**照 README 時偏離的一處**：`docker compose up -d` 拉 `lscr.io/*` 失敗（`Head "https://lscr.io/v2/…": EOF`，§6 同一個原因）。
改用同一份 image 的另一個名字 `ghcr.io/linuxserver/<image>:<tag>` 拉下來（ghcr 走 DIRECT），`docker tag` 成 compose 寫的
`lscr.io/...` 名字，再 `up -d`。compose 檔與 zip 內容沒動（zip sha256 `e2d83975…625f`）。

## 3. 精靈

### 3.1 S1：三個都選套件內（照 README，`PUID=1000`）

`.env` 只改 `DATA_ROOT=/home/cppt/berth-data`（事前不存在）；`PUID` / `PGID` 照 README 的 `id -u` / `id -g` 是 1000，
與預設相同。帶帳密的步驟照票 55 的做法走 API（代理不在瀏覽器裡輸入密碼與 key）：帳密由 `openssl rand` 產生、只在 VM 的
`~/berth-trial-42/.trial/`（600）；瀏覽器（Windows 上的 playwright，打 `http://cppt-dev.local:8383`）的 session 是 API
回的 cookie，經本機一次性 http 服務交給 playwright，值不經任何輸出。精靈語言切成 EN（照英文 README 的使用者）。

| 時間 | 事件 |
| --- | --- |
| 04:45:21 | `curl -LO …/releases/latest/download/berth-deploy.zip`、解壓、`cp .env.example .env` |
| 04:45:47 | `docker compose up -d`：拉 `lscr.io/linuxserver/prowlarr` EOF，整個 `up` 中斷（§2 的繞法） |
| 04:48:07 | `up -d`（image 已在本機）；**04:48:18 四個都 healthy**（11 秒） |
| 04:50 | 頁 1：瀏覽器選套件內（[s1-01](linux-trial-2026-10-09/s1-01-page1-bundled.jpeg)）；04:50:54 `POST /api/setup/owner` 建管理員 `owner`，1.3 秒，六步全 ok（[s1-02](linux-trial-2026-10-09/s1-02-page1-owner-done.jpeg)） |
| 04:51:52 | 頁 2：瀏覽器選套件內，連上 5.2.4（預置的白名單在 rootless 上照樣讓 Berth 進去）；04:52:20 `POST /api/setup/qbittorrent/apply` 沿用擁有者，0.36 秒（[s1-03](linux-trial-2026-10-09/s1-03-page2-login-set.jpeg)） |
| 04:52:33 | 頁 3：進頁自己跑，3 個媒體庫、3 個 `berth-*` 分類、3 條 Route 各 6/6，30 秒內完成（[s1-04](linux-trial-2026-10-09/s1-04-page3-done.jpeg)） |
| 04:53:56 | 頁 4：瀏覽器選套件內；`PUT /api/setup/indexers/login` 沿用擁有者，2.5 秒；API key 由唯讀掛載讀到 |
| 04:54:39 | 頁 4「測試推薦站，加入通過的」（`POST /api/setup/indexers/recommended`）：`checks: []`，一站都沒測——Prowlarr 的候選只有磁碟上的 5 個定義，推薦清單上的一個都不在；畫面上推薦站區只剩標題與「Do this later」（[s1-05](linux-trial-2026-10-09/s1-05-page4-no-recommended.jpeg)；§6、票 73） |
| 04:55:23 | 手動測其中 4 個（Anidex、Knaben、SubsPlease、TorrentsCSV；第 5 個是 showRSS 的 RSS 定義）：全部 `unreachable`；`berth` 容器裡打 TMDB：`SSL: UNEXPECTED_EOF_WHILE_READING` |

頁 4 的回應與測站結果：[`s1-page4.txt`](linux-trial-2026-10-09/s1-page4.txt)。頁 5（TMDB）之後沒有做：key 測不過就不存（票 45），精靈停在頁 5，送單與入庫走不到。之後在 05:03 把這一套還原成照
README 的 `.env`（§4 做完實驗之後），Route 重查 3 條 ready，然後 `docker compose down` 讓出容器名給 S2（設定與資料都在
bind mount 上，留著）。

### 3.2 S2：既有 Jellyfin 與既有 qBittorrent（`PUID=0`）

既有的兩台由這張票在同一個 rootless dockerd 上用 `docker run` 起，扮演使用者本來就在跑的服務（票 36 的做法：各自留著
原本的掛載，只多掛一條 `/data`）：

| 容器 | image | 發佈的 port | 掛載 |
| --- | --- | --- | --- |
| `s2-jellyfin` | `ghcr.io/linuxserver/jellyfin:version-12.1ubu2604` | `18096:8096` | `/config`、`/movies`、`/shows`、**`/home/cppt/berth-s2-data:/data`** |
| `s2-qbittorrent` | `ghcr.io/linuxserver/qbittorrent:latest`（`WEBUI_PORT=18080`） | `18080`、`16881` tcp / udp | `/config`、`/downloads`、**`/home/cppt/berth-s2-data:/data`** |

兩台都 `PUID=0`、`PGID=0`。Jellyfin 先以它自己的 API 跑完初始精靈（管理員 `jfadmin`）、建 Movies（`/movies`）與 Shows
（`/shows`）兩個媒體庫；qBittorrent 用 log 裡的臨時密碼登入後改成產生的密碼。帳密同樣只在 `.trial/`。

Berth 這一套另解壓一份 zip 到 `~/berth-trial-42/s2/berth`，`.env` 改 `DATA_ROOT=/home/cppt/berth-s2-data`（事前不存在）、
`PUID=0`、`PGID=0`、`COMPOSE_PROFILES=prowlarr`（README：選既有的從 profile 拿掉）。05:06:03 `up -d`，15 秒 healthy。

| 時間 | 事件 |
| --- | --- |
| 05:06 | 頁 1：瀏覽器選既有、位址 `http://host.docker.internal:18096` → 「Nothing answers at this address…」（[s2-01](linux-trial-2026-10-09/s2-01-page1-host-docker-internal-refused.jpeg)）；改 `http://192.168.50.99:18096` → 連上 12.1.0、已初始化 |
| 05:07:23 | `POST /api/setup/owner` 以 `jfadmin` 登入，0.4 秒；`api_key` ok，讀到 Movies、Shows，兩個都還沒有 Berth 路徑 |
| 05:08:05 | 頁 2（API，帶帳密）：`http://host.docker.internal:18080` → 400 `connection_failed`、`POST /api/v2/auth/login: connection refused`；`http://192.168.50.99:18080` → 200，5.2.4，`/data` 探針過（[s2-02](linux-trial-2026-10-09/s2-02-page2-existing-lan-ip.jpeg)） |
| 05:08:40 | 頁 3：畫面上勾 Movies、Shows，寫入目標用預設的「New Berth path」（`/data/library/movies`、`/data/library/shows`），按「Build and check」：**兩條 Route 各 6/6**（[s2-03](linux-trial-2026-10-09/s2-03-page3-done.jpeg)） |

之後在 `s2-jellyfin` 的媒體庫設定裡（[`s2-existing.txt`](linux-trial-2026-10-09/s2-existing.txt)），Movies 有 `/movies` 與 `/data/library/movies` 兩條、Shows 有 `/shows` 與
`/data/library/shows` 兩條：原本的路徑沒動，只多一條。兩台的掛載（`docker inspect`）仍是原本的加 `/data`。頁 4 之後沒做
（不在驗收裡，而且一樣卡在 §6 的網路）。

## 4. 擁有者與 PUID / PGID

完整輸出：[`ownership.txt`](linux-trial-2026-10-09/ownership.txt)。

### 4.1 照 README 的 `PUID=1000`

- `DATA_ROOT` 由 rootless dockerd 建（宿主上 `cppt`），Berth 的 entrypoint 看到它是空的就接手 → 宿主上變成
  `100999:100999 755`。`config/berth`、`config/jellyfin`、`config/qbittorrent`、`config/prowlarr` 也全是 100999（linuxserver
  的 init 與 Berth 的 entrypoint 各自 chown）。只有 `config` 本身是 `cppt`（dockerd 建的）。
- 頁 3 三條 Route 6/6：容器之間全都是 uid 1000，硬鏈接兩端同一個擁有者，Berth 照常運作。
- **宿主上的 cppt 寫不進自己家目錄裡的 `DATA_ROOT`**：`touch` → `Permission denied`、`mkdir` → `Permission denied`，
  也刪不掉 Berth 建的任何東西。沒有 sudo 的話，只能從容器裡改：`docker run --rm -v <路徑>:/d alpine chown -R 0:0 /d`
  把它還給 cppt（容器 root 對到 cppt；實測見 `ownership.txt` F 段：100999 的檔案 `rm` 失敗，chown 之後變 1000 就刪得掉）。

### 4.2 不一致的錯誤訊息（驗收第 3 條）

製造法：`DATA_ROOT` 事先建好、放一個檔案（所以不空，entrypoint 不接手）、擁有者 cppt，`PUID=1000`。這正是 rootless
使用者把既有媒體目錄指給 Berth 時會碰到的情況：容器裡看那個目錄是 `0:0`，Berth（uid 1000）寫不進去。

頁 3「Check again」（`POST /api/setup/routes`）：三條 Route 都停在第一項，`category failed berth_cannot_write`、
`[Errno 13] Permission denied: '/data/torrent'`，其餘 pending。畫面（[m-01](linux-trial-2026-10-09/m-01-page3-berth-cannot-write.jpeg)）：

> Berth itself cannot write to /data/torrent: the user inside the berth container (PUID / PGID in .env) has no
> write permission on that folder. … Give berth the same PUID / PGID as qBittorrent and Jellyfin, or make that
> PUID / PGID the owner of the folder on the host (chown), then press "Check again".

結論：
- **指對了**：說的是 Berth 自己（不是其他容器的掛載），點名 `.env` 的 PUID / PGID，給出問題路徑。rootful Linux 上照它做
  （`chown -R 1000:1000 <DATA_ROOT>`）就會好，也是 guide〈Linux〉原本的說法。
- **rootless 上補法不成立**：「讓那組 PUID / PGID 擁有那個資料夾」在宿主上要 chown 成 100999，cppt 沒有 sudo 做不到，
  而且做了之後自己就寫不進去（§4.1）。rootless 的補法是 `PUID=0`、`PGID=0`（§4.3）。畫面上加這一句交給票 72
  （精靈文案，zh-Hant 與 en 並列），README 與 guide 這一輪先寫上。
- 沒有看到 qBittorrent 那一端的錯：Berth 自己那一條先失敗，後面的檢查不跑。

### 4.3 `PUID=0` / `PGID=0`

同一個不一致的資料夾，`.env` 改 `PUID=0`、`PGID=0` 再 `up -d`：`qbittorrent-nox`、`jellyfin` 都以容器裡的 root 跑（linuxserver
的 init 照收、沒有警告；S2 的 Prowlarr 與 Berth 自己的行程也是 uid 0、`config/` 底下全是 `cppt:cppt`，`ownership.txt` E 段），`berth_cannot_write` 消失（`download_path`、`download_visible` ok；`library_path` 的
`directory_missing` 是換了 `DATA_ROOT`、套件內 Jellyfin 的媒體庫資料夾建在舊的根目錄底下，與 PUID 無關）。新建的目錄
宿主上全是 `cppt:cppt`。S2 從頭就用 `PUID=0`，頁 3 兩條 6/6，`DATA_ROOT` 底下全是 `cppt:cppt`。

linuxserver 官方不支援 rootless（團隊在論壇上的回覆，見來源）；`PUID=0` 是社群的做法，這一輪對 jellyfin 12.1、
qbittorrent 5.2.4、prowlarr 2.6.5 三個 image 實測可用。rootless 的容器 root 不是宿主的 root，所以不是提權。

## 5. 網路

完整輸出：[`host-gateway.txt`](linux-trial-2026-10-09/host-gateway.txt)；之後寫成 [`scripts/experiments/rootless_host_probe.sh`](../../scripts/experiments/rootless_host_probe.sh)（擁有者映射與這張表一起量），在 S2 那一套上重跑一次的輸出是 [`rootless-host-probe.txt`](linux-trial-2026-10-09/rootless-host-probe.txt)。

### 5.1 `host.docker.internal`（`host-gateway`）

`berth` 容器裡 `getent hosts host.docker.internal` 是 `172.17.0.1`，與 rootful 的 Unraid 相同，但在 rootless 下那是
RootlessKit 網路命名空間裡的 docker0。從 `berth`（`berth` 網路 172.28.0.0/16）打：

| 目標 | `host.docker.internal:<port>` | `192.168.50.99:<port>`（宿主的區網 IP） |
| --- | --- | --- |
| 既有 Jellyfin（rootless 容器，`-p 18096:8096`） | connection refused | 200（`/System/Info/Public`） |
| 既有 qBittorrent（rootless 容器，`-p 18080:18080`） | connection refused | 403（連到了、沒登入） |
| 宿主上的原生程式，監聽 `0.0.0.0:18901` | connection refused | 200 |
| 宿主上的原生程式，監聽 `127.0.0.1:18902` | connection refused | connection refused |

- rootless 的 `-p` 由 RootlessKit 在宿主上聽，容器網路裡的 `172.17.0.1` 沒有東西在聽；`--disable-host-loopback`
  讓容器也碰不到宿主的 loopback（slirp4netns 的 `10.0.2.2` 是 `Network is unreachable`）。
- **對使用者的意思**：rootless 上既有服務的位址要填宿主的區網 IP（精靈位址欄的範例本來就是 `http://192.168.1.10:8096`），
  服務要監聽 `0.0.0.0`。改 dockerd 的 `host-gateway-ip` 或關掉 `--disable-host-loopback` 都要動使用者的 Docker 設定、
  重啟 dockerd（同一台上的其他容器跟著重啟），這一輪沒有試，文件也不建議。
- 精靈的位址欄填 `localhost` 時的就地提示與測不過時的補法（同一句，brief §16.4）先推 `host.docker.internal`、
  區網 IP 排第二，沒說 rootless 上前者不通（`web/src/i18n/resources.ts` 的 `host.docker.internal` 那一句，zh-Hant 與 en）。
  rootless 使用者照第一個建議填會得到「Nothing answers at this address」（[s2-01](linux-trial-2026-10-09/s2-01-page1-host-docker-internal-refused.jpeg)）。交給票 72。

### 5.2 qBittorrent 的免密白名單

Docker 文件：rootless 的 port forwarding 預設不保留來源位址。白名單只有 Berth 的固定 IP `172.28.0.2/32`（預置腳本寫入），
所以從外面來的連線不管被改成哪個位址都進不了免密那一條：S1 套件內 qBittorrent（8080）不登入打 `/api/v2/app/version`，
VM 宿主上 403、Windows（區網）上 403。Berth 自己從 172.28.0.2 進得去（頁 2、頁 3）。

## 6. VM 的對外網路（S1 停在這裡）

指令輸出：[`network.txt`](linux-trial-2026-10-09/network.txt)（05:22 在 VM 與 Windows 上同時打同樣的網址、mihomo 的 log、Prowlarr 的錯誤）。

- `verge-mihomo` 的 TUN 接管所有連線、rule 模式：`github.com` 等少數網域 DIRECT，其餘 `Match` 走節點
  「冲上云霄 / 台湾家宽D」。04:45–05:22 之間（最後一次在 05:22）這個節點的 TLS 全部斷在握手（`unexpected eof while reading`），mihomo 的
  log 照樣記 `match Match using …`。
- 受影響的：`lscr.io`（§2 繞過）、`indexers.prowlarr.com`（Prowlarr 的站定義更新失敗，退回磁碟上的 5 個）、每一個
  索引站、`api.themoviedb.org`。從 Windows 主機打同樣的網址都正常。
- 這是使用者 VM 的代理設定，改節點或關 TUN 都是改使用者的設定，這一輪沒有動。**S1 的入庫等使用者把 VM 的網路弄通之後
  再補**：S1 那一套的 `config/` 與 `berth-data` 留在 VM 上，`docker compose up -d` 就回到頁 4。

## 7. 發現與處理

| # | 發現 | 處理 |
| --- | --- | --- |
| L1 | rootless 上 `PUID=$(id -u)` 讓宿主上的自己寫不進 `DATA_ROOT`（subuid 100999） | **本票改** README（兩份）Install 第 2 步、guide〈Linux〉、`.env.example` 的註解：rootless 填 `0` / `0`，已經跑過的怎麼用 `docker run … chown -R 0:0` 拿回來 |
| L2 | rootless 上 `host.docker.internal` 連不到宿主上的任何服務；區網 IP 可以 | **本票改** guide〈Addresses〉、compose 檔 `extra_hosts` 旁的註解；精靈的就地提示與補法交給**票 72** |
| L3 | `berth_cannot_write` 的補法（chown 給那組 PUID / PGID）在 rootless 上做不到 | **票 72**（同一批精靈文案） |
| L4 | Prowlarr 拿不到站定義時，頁 4 的推薦清單整段消失：只剩標題「Recommended sites」與「Do this later」，主鍵不見、也不說為什麼；按 API 回 `checks: []` | **票 73**。根因是 Prowlarr 連不上 `indexers.prowlarr.com`（這一輪是 VM 的代理），但在擋了那個網域的網路上一樣會發生 |
| L5 | 拉 `lscr.io` 失敗時整個 `up -d` 中斷 | 不改：這台的代理造成；`ghcr.io/linuxserver/*` 是同一份 image，記在這裡給碰到的人 |
| L6 | guide〈Host platforms〉與 README〈Status〉說「其他 Linux 沒測過」 | **本票改**：加「Ubuntu 26.04 rootless：精靈到頁 3、兩種情境的 Route 檢查；入庫沒跑」 |

## 8. 收尾

這一輪**留著**：S1 那一套（`~/berth-trial-42/berth/`，`config/`、`/home/cppt/berth-data`，容器已 `down`）等網路通了補入庫；
S2 那一套（`~/berth-trial-42/s2/`、`/home/cppt/berth-s2-data`）停在頁 4，05:3x 已 `docker compose down`、`s2-jellyfin` 與
`s2-qbittorrent` 已 `docker stop`（容器留著），讓出 `berth` 這個容器名與 port 給同一台上之後的票 71。帳密與 cookie 在 `~/berth-trial-42/.trial/`（600）。全部清掉的指令：

```bash
docker rm -f s2-jellyfin s2-qbittorrent
# S1 留下的 100999 檔案要先從容器裡還給自己，否則刪不掉（§4.1）
docker run --rm -v /home/cppt:/h alpine chown -R 0:0 /h/berth-data /h/berth-trial-42
rm -rf ~/berth-trial-42 /home/cppt/berth-data /home/cppt/berth-data-own /home/cppt/berth-s2-data
```

image（`ghcr.io/1morr/berth:latest`、四個 linuxserver 的 `ghcr.io` 與 `lscr.io` 名字）沒刪：票 70、71 在同一台上會用到。

## 來源

- Docker docs，Rootless mode › Troubleshooting：網路驅動與 port driver 的對照表、「Port forwarding with `docker run -p`
  does not propagate source IP addresses by default」、`docker inspect` 的 IP 在 RootlessKit 的命名空間裡。
  <https://docs.docker.com/engine/security/rootless/troubleshoot/>
- Docker docs，Compose › Networking：「On Linux, `host-gateway` resolves to the host's IP on the default bridge network」。
  <https://docs.docker.com/compose/how-tos/networking/>
- LinuxServer.io discourse「Setting PUID and PGID to root」：團隊回覆「We also do not support rootless」；使用者回報
  rootless 下 PUID / PGID 改 0 解決權限問題。<https://discourse.linuxserver.io/t/setting-puid-and-pgid-to-root/3726>
- LinuxServer.io，Understanding PUID and PGID。<https://docs.linuxserver.io/general/understanding-puid-and-pgid>
