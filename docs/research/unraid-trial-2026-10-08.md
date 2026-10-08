# Berth 在 Unraid 上實跑：套件內 Jellyfin 與 Emby 並存（2026-10-08，M4 票 55）

範圍：main `b10c9c7` 本機 build 的 image，部署到使用者真的在用的 Unraid（`tower`）。只在
`/mnt/user/Roxy/Berth`、`/mnt/user/appdata/berth*` 與 `berth*` 容器上寫；Emby、Jackett、既有 qBittorrent
與其他容器全程沒動（§7）。截圖與指令輸出在 [`unraid-trial-2026-10-08/`](unraid-trial-2026-10-08/)。
審計的 S1 做法見 [`usability-audit-2026-10-07.md`](usability-audit-2026-10-07.md) §3 S1。

## 1. 結論先講

- **S1（三個都選套件內）在 Unraid 上走得完、入庫成立**：`docker compose up -d` 到四個容器 healthy 約 80 秒（含拉三個
  image），精靈約 5 分鐘，送單到入庫 3 分鐘，硬鏈接 link 數 2、同一個 inode。
- **user share（shfs）上的硬鏈接成立**：條件是全域設定「Tunable (support Hard Links)」＝ Yes（`fuse_useino="yes"`，
  這台已開）。`hardlink.sh` 直接對 `/mnt/user/Roxy/Berth` 跑 PASS；Route 的六條檢查都過。README 的「mergerfs 不行」
  不適用於 Unraid 的 user share——它是 shfs，不是 mergerfs。
- **mover 之後硬鏈接還在**：21:00 的排程 mover 把兩個名字一起從 cache 搬到 disk3，仍是 links 2、同一個 inode；
  Jellyfin 照樣播得到，qBittorrent 照常做種，Berth 對帳 0 件、健康頁全綠。shfs 報的 inode 跟著換了碟而改變
  （§4.2），帳本記的那一個從此過期，目前只在一種少見的刪除情境下有影響、而且失敗在安全的一邊（U4）。
- **PUID / PGID 99 / 100 照 `.env` 生效**：`DATA_ROOT` 與 `CONFIG_ROOT` 底下 Berth 與三個服務建的每一個檔案都是
  `nobody:users`；唯一的例外是 Docker 自己建的 `CONFIG_ROOT` 本身（`root:root 755`），不影響使用。
- **原生 Linux 的 `host-gateway` 成立**：`berth` 容器裡 `host.docker.internal` 解成 `172.17.0.1`（docker0），
  打得到宿主上既有的 qBittorrent（8080）、Emby（8096）、Jackett（9117）。票 42 的那一條在 Unraid 上回答了。
- **要改的只有文件**：compose 檔與預置腳本在 Unraid 上照原樣可用（PUID / PGID、port 全靠 `.env`）。README 加
  Unraid 一節（§6）。其他發現交給後面的票（§6）。

## 2. 環境

| 項目 | 值 |
| --- | --- |
| 主機 | Unraid 7.1.4（kernel 6.12.24-Unraid）、Intel i3-8100T |
| Docker / Compose | 27.5.1 / v2.40.3（Compose Manager 外掛 2025.11.01 附的） |
| share `Roxy` | disk1–3（xfs）＋ cache（btrfs NVMe）；`shareUseCache="yes"`（cache → array），mover `0 */3 * * *` |
| 全域 share 設定 | `fuse_useino="yes"`（介面上的「Tunable (support Hard Links)」，`ShareSettings.page:139-142`） |
| image | `berth:unraid-b10c9c7`（main `b10c9c7`，本機 `docker build -f deploy/Dockerfile`；本機 id `sha256:8050bb25…08e2`，`docker load` 進 Unraid 後 id `sha256:0253b28b…3eca58e8`——兩邊的 image store 不同，id 的算法不同） |
| 其他三個 image | `lscr.io/linuxserver/jellyfin:version-12.1ubu2604`（12.1.0）、`linuxserver/qbittorrent:latest`（5.2.3）、`linuxserver/prowlarr:latest` |

部署目錄 `/mnt/user/appdata/berth-deploy/`：repo `deploy/` 的 `docker-compose.yml`、`.env.example`、`preseed/` 原樣複製，
`.env` 只改下面幾行，另加一個只換 image 的 `docker-compose.override.yml`（`berth: image: berth:unraid-b10c9c7`）。
compose 檔沒改。

```
DATA_ROOT=/mnt/user/Roxy/Berth
CONFIG_ROOT=/mnt/user/appdata/berth
PUID=99
PGID=100
JELLYFIN_PORT=18096
QBITTORRENT_WEBUI_PORT=18080
QBITTORRENT_BT_PORT=16881
（BERTH_PORT=8383、PROWLARR_PORT=9696、TZ=Asia/Taipei、COMPOSE_PROFILES 三個都開，與 .env.example 相同）
```

開工前 `ss -ltn` 確認 8383、18096、18080、16881、9696 都空著（8080、8096、6881 被既有的 qBittorrent 與 Emby 佔著，照
README 的預設值會撞）。`DATA_ROOT` 與 `CONFIG_ROOT` 事前都不存在，沒有手動建。

## 3. S1：三個都選套件內

### 3.1 時間線

| 時間 | 事件 |
| --- | --- |
| 18:38:49 | `docker compose up -d`（`docker compose pull` 先失敗：override 的本機 image 拉不到，預期內；`up` 自己拉另外三個） |
| 18:39:50 | `up -d` 結束，四個容器 Started |
| 18:40:11 | 四個都 healthy |
| 18:42:51 | 開 `http://tower:8383`，自動導到 `/setup?step=1` |
| 18:43 | 頁 1：選套件內 → 連上 12.1.0「還沒跑過自己的初始精靈」；建管理員 `owner`（API，見 3.2） |
| 18:44:31 | 頁 2：選套件內 → 連上 5.2.3、`/data` 探針過；WebUI 登入沿用擁有者（API，0.4 秒） |
| 18:45:12–18:45:46 | 頁 3：進頁自己跑，3 個媒體庫、3 個 `berth-*` 分類、3 條 Route 各 6/6，約 34 秒（審計是 20 秒） |
| 18:46:21–約 18:46:41 | 頁 4：選套件內 →「測試推薦站，加入通過的」：加入 6 站，Nyaa（連不上）、1337x、EZTV（Cloudflare）沒過，與審計相同；介面登入沿用擁有者（API，2.8 秒） |
| 18:47:39 | 頁 5：TMDB key 經 API 測過、存下（見 3.2） |
| 18:48:09 | 頁 6「完成設定」→ 探索頁，已登入 |
| 18:49:14 | 作品頁《活死人之夜》(1968) 按「搜尋」：約 25 秒，37 筆；另 107 筆名字對不上已略過、74 筆年份或類型對不上已收起來（與審計同數） |
| 18:50:15 | 送 `Night of the Living Dead (1968) 720p BRRip x264 -YTS`（790 MB，YTS）到 Movies |
| 18:53:18 | 入庫（硬鏈接）：送單後 3 分 03 秒 |
| 18:55:52 | Berth 第二次反查沒找到，改請 Jellyfin 掃描；掃描 18:56:04 完成 |
| 19:05:52 | Berth 下一次反查認到（Jellyfin item `dbdba175…`）：入庫後 12 分 34 秒 |

截圖：[s1-01](unraid-trial-2026-10-08/s1-01-page1-bundled.jpeg)、[s1-02](unraid-trial-2026-10-08/s1-02-page1-owner-done.jpeg)、
[s1-03](unraid-trial-2026-10-08/s1-03-page2-bundled.jpeg)、[s1-04](unraid-trial-2026-10-08/s1-04-page2-login-set.jpeg)、
[s1-05](unraid-trial-2026-10-08/s1-05-page3-done.jpeg)、[s1-06](unraid-trial-2026-10-08/s1-06-page4-recommended.jpeg)、
[s1-07](unraid-trial-2026-10-08/s1-07-page5-verified.jpeg)、[s1-08](unraid-trial-2026-10-08/s1-08-page6.jpeg)、
[s1-09](unraid-trial-2026-10-08/s1-09-send-confirm.jpeg)、[s1-10](unraid-trial-2026-10-08/s1-10-jobs.jpeg)、
[s1-11](unraid-trial-2026-10-08/s1-11-title-imported.jpeg)、[s1-12](unraid-trial-2026-10-08/s1-12-reconcile-before-mover.jpeg)、
[s1-13](unraid-trial-2026-10-08/s1-13-health-before-mover.jpeg)。

### 3.2 和審計做法不同的地方

**帶帳密的四步改走 API，其餘在瀏覽器點**：`tower` 不是 localhost，代理在瀏覽器裡不輸入密碼與 API key。所以：

- 頁 1 建管理員是在 Unraid 上 `curl -X POST localhost:8383/api/setup/owner`（帳密由 `openssl rand` 產生，只存在
  `/mnt/user/appdata/berth-deploy/CREDENTIALS.md` 與同目錄 `.trial/pw`，兩者 600、不進 repo；`.trial/` 收尾時刪了）。
- 瀏覽器的 session 是把那一次回的 `berth_session` cookie 交給 playwright（經本機一次性 http 服務，值不經工具輸出）。
- 頁 2、頁 4 的介面登入是 `POST /api/setup/qbittorrent/apply`、`PUT /api/setup/indexers/login`，都帶 `reuse_owner`。
- TMDB key 從 repo 的 `.env` 經 ssh stdin 送給 Unraid 上的 `curl`，任何輸出都沒有它。

所以頁 1、2、4、5 的打字與按鍵數沒有量，這一輪也不是量這個（審計 S1 量過）。頁 3、頁 4 的推薦站、頁 6、搜尋與
送單都是在畫面上按的。

### 3.3 Jellyfin

- 入庫後作品頁寫「Jellyfin 還在掃描，Berth 下一次確認在 1 分鐘後」（審計 P1-9，票 62）。Berth 在第二次反查沒找到後
  才請整庫掃描（18:55:52），Jellyfin 的掃描 12 秒後（18:56:04）就完成，但帳本的下一次反查已經退避到 19:05:52。
  從入庫到作品頁說「Jellyfin 已收錄」共 12 分 34 秒；審計 S1 是 3 分鐘左右，差在第二次反查與掃描的先後。
  這不是 Unraid 特有的，記給票 62（U8）。
- 19:07 作品頁：「帳本 對得上 · Jellyfin 已收錄」、「在 Jellyfin 看」連到 `http://tower:18096/web/#/details?id=…`
  （[s1-14](unraid-trial-2026-10-08/s1-14-title-jellyfin-found.jpeg)）。
- **Jellyfin 播得到**：在 `berth` 容器裡用 Berth 存的 API key 問 Jellyfin（[`scripts/experiments/jellyfin_stream_probe.py`](../../scripts/experiments/jellyfin_stream_probe.py)，
  key 不印出）：片名、TMDB 10331、路徑是 `/data/library/movies/…`、96.6 分鐘，`/Videos/{id}/stream?static=true` 帶
  `Range: bytes=0-1048575` 回 206、1 MiB（[`jellyfin-before-mover.txt`](unraid-trial-2026-10-08/jellyfin-before-mover.txt)）。

## 4. 硬鏈接與 mover

### 4.1 入庫當下（18:53:46）

輸出：[`hardlink-after-import.txt`](unraid-trial-2026-10-08/hardlink-after-import.txt)。指令（在 tower 上，mover 後那一次相同）：

```bash
cd /mnt/user/Roxy/Berth
find . -type f -size +10M -exec stat -c "%d %i %h %U:%G %a %s %n" {} \;          # shfs 看到的
for m in /mnt/cache /mnt/disk1 /mnt/disk2 /mnt/disk3; do                          # 實際在哪顆碟
  find $m/Roxy/Berth -type f -exec stat -c "$m %d %i %h %s %n" {} \; 2>/dev/null
done
```

收尾時另把其餘幾條宣稱（全域設定、`hardlink.sh`、mover 時間、`in_use`、擁有者、`host.docker.internal`、qBittorrent 狀態、Emby 的掛載、port）連同指令重跑一次，存在 [`checks-at-close.txt`](unraid-trial-2026-10-08/checks-at-close.txt)。

| 路徑 | 在哪裡 | `st_dev` | inode | links |
| --- | --- | --- | --- | --- |
| `/mnt/user/Roxy/Berth/library/movies/Night of the Living Dead (1968) [tmdbid-10331]/… - [BD][720p][YTS.AM].mp4` | shfs | 42 | 11258999075244504 | 2 |
| `/mnt/user/Roxy/Berth/torrent/complete/movies/Night Of The Living Dead (1968) [BluRay] [720p] [YTS.AM]/….mp4` | shfs | 42 | 11258999075244504 | 2 |
| 同上兩個，在 `/mnt/cache/Roxy/Berth/…` | cache（btrfs） | 40 | 6818264 | 2 |

- 兩個名字都在 cache 上，陣列碟上沒有。
- **shfs 的 inode 是合成的**：`11258999075244504 = 40 << 48 | 6818264`，高位是底下那顆碟的 `st_dev`，低位是它的 inode。
  所以 Berth 帳本記的 `(dev, inode)` = `(42, 11258999075244504)`，**檔案被 mover 搬到別顆碟之後，shfs 報的 inode
  會跟著變**（推論，見 4.2 實測）。
- 另外直接在宿主上跑 README 的 `sh hardlink.sh /mnt/user/Roxy/Berth`：PASS，dev 42、nlink 2（18:52 跑一次，收尾 22:03 再跑一次也 PASS，見 `checks-at-close.txt`）。

### 4.2 mover 之後

排程 mover（`0 */3 * * *`）在 21:00 跑；這台沒開 mover log（`shareMoverLogging="no"`），時間由 disk3 上檔案的建立時間
（birth `21:00:01`，mtime 仍是 `18:53:13`）確認。沒有手動跑 mover。21:14 重記（指令同 §4.1，輸出：
[`hardlink-after-mover.txt`](unraid-trial-2026-10-08/hardlink-after-mover.txt)）：

| 路徑 | 在哪裡 | `st_dev` | inode | links |
| --- | --- | --- | --- | --- |
| library 與 complete 兩個名字 | shfs | 42 | 649362777713998419 | 2 |
| 同上兩個，在 `/mnt/disk3/Roxy/Berth/…` | disk3（xfs） | 2307 | 6442515027 | 2 |
| `/mnt/cache`、`/mnt/disk1`、`/mnt/disk2` | — | — | 沒有這兩個檔 | — |

- **硬鏈接還在**：mover 把同一個 inode 的兩個名字一起搬到同一顆碟，links 仍是 2（與 TRaSH「用 cache 時硬鏈接
  保持」一致）。附帶的 `www.YTS.AM.jpg` 也搬了。cache 上只剩空目錄。
- **shfs 的 inode 變了**：`649362777713998419 = 2307 << 48 | 6442515027`，高位換成 disk3 的 `st_dev`。帳本還是
  `(42, 11258999075244504)`。影響見 U4。
- 搬的那一刻沒有東西開著這個檔（18:53 之後沒有 peer）：Unraid 的 `in_use`（`fuser` 加 `losetup`）在 19:10、21:14 與 22:03
  都回「沒在用」。**做種中正被讀的檔，mover 會跳過**（`/usr/local/sbin/mover` 的註解、TRaSH），那一次就留在 cache、
  下一輪再搬；兩個名字仍在同一顆碟上，硬鏈接不受影響。
- **Jellyfin 照樣播得到**：同一支 `jellyfin_stream_probe.py` 再問一次，路徑不變、`stream` 206、1 MiB
  （[`jellyfin-after-mover.txt`](unraid-trial-2026-10-08/jellyfin-after-mover.txt)）。容器看到的是 `/data/...`（shfs），
  底下換碟對它透明。
- **qBittorrent 照常**：`torrents/info` 是 `stalledUP`、progress 1、`save_path` `/data/torrent/complete/movies`，沒有
  `missingFiles`。

### 4.3 Berth 的帳與健康

- 入庫後手動「立刻對帳」（18:56:43）：帳本、qBittorrent、COMPLETE、媒體庫各比了 1 筆，開了 0 件。
- 健康頁全綠：三個服務已繫上，三條 Route 各 6/6。
- **mover 之後**（21:15）：再按「立刻對帳」，帳本、qBittorrent、COMPLETE、媒體庫、Jellyfin 各比了 1 筆，開了 0 件
  （[s1-15](unraid-trial-2026-10-08/s1-15-reconcile-after-mover.jpeg)）。對帳比的是來源與目標**現在**的
  `(dev, inode)`（`reconcile.py:433`），兩邊一起換了，所以對得上。健康頁「立即重測」全綠，三條 Route 各 6/6
  （[s1-16](unraid-trial-2026-10-08/s1-16-health-after-mover.jpeg)）。

## 5. 權限與網路

### 5.1 擁有者

- `DATA_ROOT`（事前不存在）由 Docker 建立、Berth 的 entrypoint 接手成 `nobody:users 755`；底下所有目錄 `755`、檔案
  `644`，全部 `nobody:users`（`find ! -user nobody -o ! -group users` 只找到 `CONFIG_ROOT` 本身）。
- `CONFIG_ROOT` 本身 `root:root 755`（Docker 建的），底下 `berth`、`jellyfin`、`qbittorrent`、`prowlarr` 與 638 個檔案
  全部 `nobody:users`。
- **Emby 看不到 Berth 的媒體庫**：`emby-amilys` 只掛 `/mnt/user/Roxy/Library:/Library`（與 `/config`），`/mnt/user/Roxy/Berth` 不在它的掛載裡。要讓 Emby 也看得到，得在它的模板加一條 Path，這一輪照「Emby 不動」沒有做。
- **從 SMB 看得到、改不了**：這台 Windows 以 `\\tower\Roxy\Berth\library\movies\…` 列得出入庫的檔案。Berth 的檔案是
  `644` / `755`（`UMASK=022`），既有的 `Roxy/Library` 多半是 `666` / `777`（Unraid 的「New Permissions」慣例）；使用者既有的
  qBittorrent 也是 `UMASK=022`，所以這是同一個取捨，不改預設。要從 SMB 刪改 Berth 的檔案，`.env` 設 `UMASK=000`。
- `berth.db` 是 `644`。`appdata` 這個 share 沒有 SMB / NFS 匯出（`shareExport="-"`），能讀它的只有宿主上的 root；
  README〈秘密與備份〉說的「靠檔案權限保護」在 Unraid 上成立的前提是 appdata 不匯出。
- PUID / PGID 不一致時的錯誤訊息（票 42）：這一輪兩者一致，沒有製造。

### 5.2 `host.docker.internal`

```
$ docker exec berth getent hosts host.docker.internal
172.17.0.1      host.docker.internal
$ ip -4 addr show docker0
    inet 172.17.0.1/16 brd 172.17.255.255 scope global docker0
```

從 `berth` 容器以 Python `urllib` 打宿主上的既有服務（只讀、不登入）：

| URL | 結果 |
| --- | --- |
| `http://host.docker.internal:8080/api/v2/app/version`（既有 qBittorrent） | 403 `Forbidden`，帶 qBittorrent 的 `content-security-policy`：連到了，沒登入所以 403 |
| `http://host.docker.internal:8096/System/Info/Public`（Emby） | 200，`"Version":"4.9.5.0"` |
| `http://host.docker.internal:9117/UI/Login`（Jackett） | 400：連到了 |

`docker0` 是預設 bridge 的閘道，而 Berth 在自己的 `berth` 網路（172.28.0.0/16）；宿主上發佈的 port 綁在
`0.0.0.0`，所以從另一個 bridge 走 172.17.0.1 一樣連得到。

## 6. 發現與處理

| # | 發現 | 處理 |
| --- | --- | --- |
| U1 | README 沒有 Unraid：`.env` 的 PUID / PGID 預設 1000、三個 port 與常見的既有服務撞、「mergerfs 不行」讓人以為 user share 不行、沒說 hardlink 那個全域設定 | **本票改 README**〈支援的宿主平台〉〈硬鏈接前提〉，加 Unraid 的做法 |
| U2 | Compose Manager 的 stack 檔預設放在 `/boot/config/plugins/compose.manager/projects/<名字>/`（隨身碟，vfat、`fmask=0177`：檔案 600、不可執行）；`.env.example` 的 `./data`、`./config` 會落在隨身碟上 | README 寫：部署目錄放 `/mnt/user/appdata/berth-deploy`，用 Compose Manager 的話「Add New Stack」名字填 `berth`、在 Advanced 填 Indirect Path 指到那個目錄（讀外掛原始碼 `exec.php`、`compose_util.php` 推論：indirect stack 以 `-p <stack 名>` 跑該目錄所有 `*compose*.yml`、`.env` 從該目錄讀；**沒有在 UI 上實按**，註冊會寫進 `/boot`，超出本票範圍） |
| U3 | 部署用了 override 時，Compose Manager 的 indirect stack 以 `find` 的順序把目錄裡所有 `*compose*.yml` 加成 `-f`，base 與 override 的先後不保證 | 只影響自己 build image 的人；記下，不改 |
| U4 | 帳本的 `(dev, inode)` 在 Unraid 上是 shfs 合成的值，mover 搬碟後就過期（§4.2 實測：`11258999075244504` → `649362777713998419`）。讀它的只有刪除（`deletion.Placed.holds`，`deletion.py:381`）：先比帳本記的、再比來源現在的。Berth 自己的刪除先拆媒體庫鏈接、後刪來源（`_apply`），那時來源還在，認得出。**失效條件**：使用者在 qBittorrent 連檔案一起刪了 torrent、mover 又搬過，之後在 Berth 刪這部作品——媒體庫那一份被當成使用者的檔案、留著並列為「不是 Berth 放的」。失敗在安全的一邊 | 沒在這台製造（要刪使用者會看到的檔案）；寫不出 Berth 自己就會走到的路徑，不開票，記給拆下一批票時決定 |
| U9 | 健康頁「最後成功 2 秒後」：瀏覽器那台的時鐘比 Unraid 慢兩秒，相對時間就說成未來 | 文案，記給票 68 |
| U5 | 頁 5 TMDB「這裡能做」寫「測不過的 key 照樣存下來」（`web/src/i18n/resources.ts:93`，en `:3226`），與票 45「測過才存」相反 | 文案，交給票 68 |
| U6 | 使用者以前用過的 CA Jellyfin 模板（`jellyfin/jellyfin`）把媒體掛在 `/data/tvshows`、`/data/movies`；之後若改接既有 Jellyfin，Berth 要的 `/data` 會與它們成為巢狀掛載 | 交給票 63（Unraid「Add another Path」的補法要提）；沒實測 |
| U8 | 空媒體庫第一次入庫到「Jellyfin 已收錄」12.5 分鐘：Berth 請掃描的那一刻就把下一次反查排到 10 分鐘後，掃描 12 秒就完成了 | 交給票 62（掃描範圍那張會動同一段） |
| U7 | 頁 3 自跑 34 秒，比審計的 20 秒慢：第一條 Route 停在「qBittorrent 讀得到 Berth 寫的檔案」約 25 秒（校驗探測檔） | 不擋；機器較慢（i3-8100T、檔案在 shfs） |

## 7. 既有容器沒被動過

開工（18:37）與收尾各存一次 `docker ps -a` 與 `docker inspect` 摘要（id、image、啟動時間、狀態、重啟次數、掛載）：
[`containers-before.txt`](unraid-trial-2026-10-08/containers-before.txt)、[`containers-after.txt`](unraid-trial-2026-10-08/containers-after.txt)。

開工時 14 個既有容器、收尾時多了 4 個 `berth*`。把每列的掛載排序、去掉行尾空白之後比對，**14 個既有容器的
id、image、啟動時間、狀態、重啟次數與掛載完全相同**（`docker inspect` 的掛載順序每次不同，所以要先排序）。
`emby-amilys`、`qbittorrent`、`jackett` 的啟動時間都還是 2026-09-15。

## 8. 收尾

使用者開工時就說這一套留著：沒有 `docker compose down`，`/mnt/user/Roxy/Berth`、`/mnt/user/appdata/berth`、
`/mnt/user/appdata/berth-deploy` 都在。它跑的是本機 build 的 `berth:unraid-b10c9c7`（override 檔指定）；之後要換成
GHCR 上的版本，刪掉 `docker-compose.override.yml` 再 `docker compose pull && docker compose up -d`。測試帳密在
`/mnt/user/appdata/berth-deploy/CREDENTIALS.md`（600）。這一輪 API 呼叫的暫存（同目錄 `.trial/`：cookie、帳密、
回應）收尾時刪了。

## 來源

- Unraid 7.1.4 宿主上的檔案（只讀）：`/usr/local/emhttp/plugins/dynamix/ShareSettings.page`（`fuse_useino` 的介面名稱）、
  `/usr/local/sbin/mover`（in use 的檔案不搬、metadata 保留）、`/usr/local/emhttp/plugins/compose.manager/php/exec.php`、
  `php/compose_util.php`、`scripts/compose.sh`（indirect stack、`-p`、`-d`）。
- TRaSH Guides：Unraid 的單一 share、cache 與 mover 的硬鏈接、做種中的檔案 mover 搬不動。
  <https://trash-guides.info/File-and-Folder-Structure/How-to-set-up/Unraid>
- Compose Manager 的 Indirect Path 以宿主上裝的外掛（2025.11.01）原始碼為準（上面第一條）；同名功能在 Plus 分支 README 的說明可對照：<https://github.com/mstrhakr/compose_plugin>（不是這台裝的那一個）。
