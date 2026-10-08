# 55 — Unraid 實跑：Berth 帶自己的 Jellyfin，與 Emby 並存

**Status:** done

**Blocked by:** 無（用本機 build 的 image 傳到 Unraid，不等 0.2.0）

**讀:** `docs/research/usability-audit-2026-10-07.md` §6.3（Unraid 補述）、§3 S1（照它的做法與量測）、附錄 B（目錄樹）；brief §16.1、§20.7（硬鏈接）、§20.14；README〈硬鏈接前提〉〈支援的宿主平台〉；票 42（原生 Linux 的驗收項，這張先在 Unraid 上回答其中能回答的）

## 為什麼

- 使用者實際要跑 Berth 的機器是 Unraid（2026-10-08）。第四輪審計全部在 Windows Docker Desktop 跑，所以「你自己用」在 Unraid 上是未驗證。
- 使用者拍板走 (a)：Berth 帶自己的 Jellyfin（套件內），與現有的 Emby 並存；Emby、Jackett、現有的 qBittorrent 都不動。換到 Jellyfin 是之後的決定。
- Unraid 和審計環境不同、沒有驗過的：
  - user share（shfs）上的硬鏈接；
  - cache 加上 mover 搬到陣列之後硬鏈接還在不在；
  - PUID / PGID 99 / 100（`nobody:users`）；
  - 原生 Linux 的 `host-gateway`；
  - 官方 compose 在 Compose Manager 外掛下怎麼用。

## 已查到的現況（2026-10-08，`ssh root@tower` 只讀）

- **主機**：Unraid 7.1.4、Docker 27.5.1、Compose v2.40.3；Compose Manager 外掛已裝（`/boot/config/plugins/compose.manager/projects/` 下有 immich 等 7 個 stack）。
- **連線**：
  - 指令：`ssh -F /dev/null -i ~/.ssh/unraid-tower-ed25519 root@tower`。
  - **要帶 `-F /dev/null`**：使用者的 `~/.ssh/config` 開頭有 UTF-8 BOM，Git Bash 的 ssh 會拒讀；不要替使用者改那個檔。
- **現有容器（不准動）**：
  - `emby-amilys`（8096、8920，掛 `/mnt/user/Roxy/Library:/Library`）；
  - `qbittorrent`（8080、6881，PUID 99 / PGID 100，掛 `/mnt/user/Roxy/Downloads:/downloads` 與 `/mnt/user/Roxy/Library:/Library`）；
  - `jackett`（9117）；
  - 其餘的 syncthing、immich 等都與這張無關。
- **已占用的 port**：22 53 80 139 443 445 3133 3702 5355 5700 5900 6881 8080 8088 8096 8317 8384 8443 8920 9117 16509 22000 60002。
- **Docker 子網**：172.17 / 18 / 20 / 21、br0 192.168.50.0/24。Berth 的 172.28 不撞；容器名 `berth*` 也不撞。
- **share `Roxy`**：
  - 跨 disk1–3（xfs）加 cache（btrfs NVMe）；`shareUseCache="yes"`，mover 每 3 小時跑一次（`0 */3 * * *`）；highwater 分配、沒有 split level。
  - 全域 `fuse_useino="yes"`。
  - `Roxy/Library` 已有 602 個 link 數大於 1 的檔案（硬鏈接在 user share 上看起來可用，**推論**）。
- **目標路徑都還不存在**：`/mnt/user/Roxy/Berth`、`/mnt/user/appdata/berth`。

## 做什麼

1. **部署**（照一般使用者的做法，只改 `.env`，不改 compose 檔）：
   - 把 repo `deploy/` 的 `docker-compose.yml`、`.env.example`、`preseed/` 複製到 `/mnt/user/appdata/berth-deploy/`。
   - image：用 main HEAD build 一份，`docker save | ssh … docker load` 傳過去，tag 成 compose 要的那一個；或加一個只換 image 的 override。記下 digest 與 commit。
   - `.env`：
     - `DATA_ROOT=/mnt/user/Roxy/Berth`（和 Downloads、Library 同一個 share，cache 規則一樣，正好驗 mover）；
     - `CONFIG_ROOT=/mnt/user/appdata/berth`；
     - `PUID=99`、`PGID=100`、`TZ=Asia/Taipei`；
     - `BERTH_PORT=8383`、`JELLYFIN_PORT=18096`、`QBITTORRENT_WEBUI_PORT=18080`、`QBITTORRENT_BT_PORT=16881`、`PROWLARR_PORT=9696`（開工前用 `ss -ltn` 再確認一次都空著）；
     - `COMPOSE_PROFILES` 三個都開。
   - 在 `/mnt/user/appdata/berth-deploy` 下 `docker compose up -d`。另外看 Compose Manager 的 UI 能不能認領這個 stack，只記錄、不強求。
2. **S1（三個都選套件內）**：從這台 Windows 用 playwright 開 `http://tower:8383` 走完精靈。
   - TMDB key 照審計的做法：`keysrv.py` 加 `fetch`，key 不能出現在任何工具輸出。
   - 送一部公有領域電影入庫：《Night of the Living Dead》(1968) 或審計 S3 的清單；不要下載有版權的東西。
   - 量時間；確認 Jellyfin（`http://tower:18096`）看得到。
3. **硬鏈接與 mover**：
   - 入庫後在 Unraid 上記錄：complete 與 library 兩個檔的 inode 與 link 數，以及它們實際在 `/mnt/cache` 還是 `/mnt/diskN`（`ls -i`、`stat`）。
   - 等排程 mover 跑過（每 3 小時）再記一次：link 數還是不是 2、兩個檔是不是在同一顆碟、Jellyfin 還播不播得到。
   - Berth 的對帳（手動觸發）與健康頁說什麼。
   - **不要手動跑 `mover`**：它會搬整台的 cache，要的話先問使用者。
4. **權限**：看 `DATA_ROOT` 與 `CONFIG_ROOT` 下新建檔案的擁有者與權限（應是 99:100）；Emby 或使用者從 SMB 看不看得到。PUID / PGID 不一致時的錯誤訊息（票 42 的驗收項）：在這台上**只觀察、不刻意製造**。要製造就另開一個隔離的 `DATA_ROOT`，跑完刪掉。
5. **原生 Linux 的 `host-gateway`**：在 `berth` 容器裡 `getent hosts host.docker.internal`，並從 Berth 打一次宿主上 qBittorrent 的 `/api/v2/app/version`（只讀，不登入）。這樣能回答票 42 的那一條。
6. **找到的問題**：屬於 compose、預置腳本、README 的能在這張修就修；其餘記下來，交給後面拆的票。
7. **收尾**：問使用者要不要留著這一套（它可能就是之後真的在用的 Berth），還是 `docker compose down` 並刪掉兩個目錄。**沒得到回答前不刪。**

## 驗收

- [x] Unraid 上 S1 走完並入庫一部；附截圖（`docs/research/unraid-trial-<日期>/`）與指令輸出
- [x] 硬鏈接在 user share 上成立（link 數 2、同 inode）；mover 跑過之後的結果實測並寫下（成立或不成立都算完成，不成立就開票）
- [x] 新建檔案的擁有者是 99:100，結論寫進研究檔
- [x] `host.docker.internal` 在原生 Linux（Unraid）上解得到、連得到宿主服務
- [x] 結果寫成 `docs/research/unraid-trial-<日期>.md`；結論摘進 brief §20.14（附來源與指令）；README〈支援的宿主平台〉與〈硬鏈接前提〉照結果改（「mergerfs 不行」對 Unraid user share 怎麼說）
- [x] 現有的 `emby-amilys`、`qbittorrent`、`jackett` 與其他容器全程沒被動過（開工與收尾各存一次 `docker ps -a` 與 `docker inspect` 摘要比對）
- [x] progress.md 記一行；有改程式時，全部檢查與 test 綠燈

## 規則

- **這是使用者真的在用的伺服器**：
  - 只在 `/mnt/user/Roxy/Berth`、`/mnt/user/appdata/berth*` 與 `berth*` 容器上寫。
  - 不重啟 Docker、不動陣列、不改 share 或全域設定、不手動跑 mover。
  - 要越界就先問。
- 測試帳密寫在 `/mnt/user/appdata/berth-deploy/CREDENTIALS.md`（不進 repo）。

## Comments

- 2026-10-08 實跑完成，全文在 `docs/research/unraid-trial-2026-10-08.md`。一句話：官方 compose 只改 `.env` 就在 Unraid 7.1.4 上走完 S1；user share 上硬鏈接成立，21:00 的排程 mover 把兩個名字一起搬到 disk3 之後仍是 links 2、Jellyfin 照樣播、對帳 0 件。
- **帶帳密的四步改走 API**（頁 1 建管理員、頁 2 / 4 介面登入、頁 5 TMDB key）：`tower` 不是 localhost，代理不在瀏覽器裡輸入密碼與 key；瀏覽器的 session 是 API 回的 cookie。所以這一輪沒有量頁 1、2、4、5 的按鍵數（審計 S1 量過）。
- 「PUID / PGID 不一致時的錯誤訊息」（票 42）：照規則只觀察、沒有製造；這一輪兩者一致。
- 交給後面的票（研究檔 §6）：U5 頁 5 TMDB 文案「測不過的 key 照樣存下來」與票 45 相反 → 票 68；U9 健康頁時鐘差兩秒說「2 秒後」→ 票 68；U8 空媒體庫第一次入庫 12.5 分鐘才認到（請掃描時就退避 10 分鐘）→ 票 62；U6 CA 的 Jellyfin 模板掛 `/data/tvshows`、`/data/movies`，與 Berth 要的 `/data` 成巢狀 → 票 63。
- U4（帳本的 shfs inode 在 mover 後過期）不開票：只有「使用者在 qBittorrent 連檔刪 torrent＋mover 搬過＋之後在 Berth 刪作品」會碰到，結果是媒體庫那一份留著（安全的一邊），留給拆下一批票時決定。
- ~~這一套照使用者開工時的答覆留著~~ **2026-10-09 依使用者要求已全部退回**（使用者之後自己從頭部署）：`docker compose down -v`（含 override），刪 `/mnt/user/appdata/berth-deploy`、`/mnt/user/appdata/berth`、`/mnt/user/Roxy/Berth` 與這張票 load / pull 的三個 image（berth、prowlarr、jellyfin；qbittorrent 那個是既有容器在用的，沒刪）。比對：14 個既有容器與開工快照完全一致、三個路徑已不存在、8383 / 18096 / 18080 / 16881 / 9696 已釋放（研究檔 §8、`containers-rollback.txt`）。
- 收尾檢查（2026-10-08 22:0x）：`pre-commit run --all-files` 全過；`uv run pytest` 3642 passed、1 failed——`tests/integration/test_rss_api.py::TestTheFirstRound::test_preview_then_follow_from_now`，單獨重跑三次都過，是全套負載下的時序不穩，與本票無關（本票只動文件與一支實驗腳本）。直接用 `.venv/Scripts/python -m pytest` 跑時 `test_cli` 的 console script 測試會因 PATH 沒有 venv 而紅，要照 README 用 `uv run`。
- code-review（Standards / Spec 兩軸）處理：實驗腳本的指令補進根 README〈實驗腳本〉、experiments README 的可攜性例外補上這支、`_api_key` 遞迴改成直接讀扁平的 `api_key`、錯誤字串改英文；研究檔修 image id 抄錯、補 stat 指令與 `checks-at-close.txt`（其餘宣稱連指令重跑一次）、補「Emby 看不到」（它只掛 `Roxy/Library`）、來源標明 Plus 分支不是這台裝的。沒處理：mover 的數字在研究檔、brief、progress、票四處各寫一次（照這個 repo 的慣例，brief 是摘要、progress 是索引）。
