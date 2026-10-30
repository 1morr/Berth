# 部署檔與 Jellyfin 身分的查證（ServerId、release 附件、preseed 內嵌）

從 design-brief §20.15、§20.17、§20.18 搬來（原文不改字）。

### 20.15 「同一台 Jellyfin」怎麼認：ServerId（2026-09-30 查證＋實測，M4 票 18）

- **`GET /System/Info/Public` 的 `Id` 就是伺服器的 `SystemId`**，匿名讀得到。原始碼：`SystemManager` 把 `Id` 設成 `ApplicationHost.SystemId`，它是 `DeviceId.Value`——第一次啟動時產生一個 GUID 寫進 **`<DataPath>/device.txt`**，之後都從那個檔讀（類別說明「the persistent unique identifier of this server installation」）。【[DeviceId.cs @ v12.1](https://github.com/jellyfin/jellyfin/blob/v12.1/Emby.Server.Implementations/Devices/DeviceId.cs)、[ApplicationHost.cs @ v12.1](https://github.com/jellyfin/jellyfin/blob/v12.1/Emby.Server.Implementations/ApplicationHost.cs)（`SystemId => _deviceId.Value`）】
- **實測（berth-existing，linuxserver 12.1.0 與 10.10.7；`scripts/experiments/jellyfin_server_id.py`）**：同一台用 `localhost`、`127.0.0.1`、從另一個容器用 `host.docker.internal` 連，`Id` 都一樣；`docker restart` 之後不變；`docker compose up -d --force-recreate` 重建容器之後也不變（`/config` 掛載還在），`device.txt` 的內容就是那個值。三台不同的 Jellyfin 各自不同。
- **`ServerName` 不能拿來認**：沒設過時它是容器的 hostname，重建容器就變（同一次實測 `dc2288726bbe` → `135a4ae43523`）。
- 所以 Berth 以 `Id` 判「同一台」：擁有者成立時記下，之後換位址只接受 `Id` 相同的（[ADR-0012](../adr/0012-owner-is-jellyfin-admin.md)、plan §9.3）。擁有者成立**之前**也用它：頁 1 的表單帶回測過的位址與 `Id`，與存下的不同就不送帳密（M4 票 28；未初始化的那一台也有 `Id`）。清掉 `/config`（或複製別人的 `/config`）的那一台會換 `Id`（或撞 `Id`）——前者等於一台新的伺服器，擁有者帳號也不在了；後者不防。



### 20.17 部署檔的 release 附件與「最新版」連結（2026-10-08 查證，M4 票 56）

> **2026-10-09 被取代、2026-10-13 部分恢復**：M4 票 71 把部署改成只用 compose 檔加 `.env`、不附檔案（zip 拿掉，見 §20.18 與 §19 E4）；M4 票 97 恢復附件，但只附那兩個純文字檔 `docker-compose.yml`、`example.env`，不附 zip（§19 2026-10-13 那一列）。下面講 `latest/download` 那一條裡的 zip 已不存在，其餘事實照用。

- **開頭是 `.` 的附件名會被 GitHub 改掉**（2026-10-13 查證，M4 票 97）：REST API〈Upload a release asset〉——「GitHub renames asset filenames that have special characters, non-alphanumeric characters, and leading or trailing periods」，改成什麼沒有寫，「List release assets」回的是改過的名字（[docs.github.com](https://docs.github.com/en/rest/releases/assets#upload-a-release-asset)）；同名附件再傳是 422，要先刪（`gh release upload --clobber` 就是先刪再傳）。所以 `deploy/.env.example` 照 Immich 以 `example.env` 上傳，名字由 Berth 決定、不靠 GitHub 改。`gh release upload` 的附件名就是本機檔名（`#` 後面只是顯示用的 label），release workflow 先把兩個檔 `cp` 成要的名字再傳。

- **`https://github.com/<owner>/<repo>/releases/latest/download/<附件名>` 直接下載最新版本的那個附件**：GitHub 文件〈Linking to releases〉寫明手動上傳的附件用這個後綴（[docs.github.com](https://docs.github.com/en/repositories/releasing-projects-on-github/linking-to-releases)）。所以每一版都要有一個**同名**的附件，README 才能寫死連結；Berth 每一版附兩份同內容的 zip：`berth-deploy-<版本>.zip` 與 `berth-deploy.zip`。Immich 的安裝步驟就是這樣拿 compose 與 `example.env`（`wget -O docker-compose.yml https://github.com/immich-app/immich/releases/latest/download/docker-compose.yml`，[docs.immich.app](https://docs.immich.app/install/docker-compose)；審計 R2 §1.6）。
- **「最新」只算正式版本**：REST API〈Get the latest release〉——「the most recent non-prerelease, non-draft release, sorted by the `created_at` attribute」；`make_latest` 對草稿與預發佈無效（「Drafts and prereleases cannot be set as latest」）（[docs.github.com](https://docs.github.com/en/rest/releases/releases#get-the-latest-release)）。所以 `-rc` 的 release 標成 prerelease 就不會動到 `latest/download`，與 GHCR 的 `:latest` 規則一致。
- **`gh release create`**：`--prerelease`、`--verify-tag`（tag 不在遠端就中止）；`gh release upload --clobber` 先刪同名附件再傳（[cli.github.com](https://cli.github.com/manual/gh_release_create)）。**帶附件的 `create` 先建草稿、傳完附件才發佈，失敗時刪掉草稿**（`draftWhileUploading`，[create.go](https://github.com/cli/cli/blob/trunk/pkg/cmd/release/create/create.go)），所以 `latest/download/` 不會有一段指到還沒有附件的新版。release workflow 用它建 release；release 已存在（重跑、手動先建）時改用 `upload --clobber`。


### 20.18 preseed 腳本內嵌進 compose：`configs.content` 加 `mode`（2026-10-09 查證＋實測，M4 票 70）

部署要只剩 compose 檔加 `.env`（使用者 2026-10-09 拍板，推翻 §19 E4），qBittorrent 的白名單腳本因此不能再是 compose 旁邊的 `preseed/` 目錄。

- **Docker 文件**：頂層 `configs` 的 `content` 從 Compose 2.23.1 起支援，內容會做變數展開（[configs](https://docs.docker.com/reference/compose-file/configs/)、[v2.23.1](https://github.com/docker/compose/releases/tag/v2.23.1)）；預設擁有者是容器執行的使用者、權限 0444。服務 `configs` 長語法的 `uid` / `gid` / `mode` 可覆寫，「Writable bit must be ignored. The executable bit can be set.」（[services#configs](https://docs.docker.com/reference/compose-file/services/#configs)）。文件沒說非 swarm 下 `mode` 有沒有效。
- **linuxserver 的 init 只執行 `-x` 的檔**：image 內 `/etc/s6-overlay/s6-rc.d/init-custom-files/run` 對 `/custom-cont-init.d/*` 做 `[[ -x ]]`，不是就印 `is not an executable file` 跳過，是就 `/bin/bash <檔>`（shebang 無關）。`/docker-mods` 的 `tamper_check`（`MOD_SCRIPT_VER 3.20250825`）對非 root 擁有、others 可寫只印警告框，**不擋**。所以 0444 的預設一定不會跑，`mode` 是成敗關鍵。讀法：`docker run --rm --entrypoint cat lscr.io/linuxserver/qbittorrent:latest /etc/s6-overlay/s6-rc.d/init-custom-files/run`（`/docker-mods` 同理）。票上列的替代寫法（入口改 `bash /custom-cont-init.d/...`、`content` 只放一行 `exec bash` 呼叫）放在 `/custom-cont-init.d` 裡同樣要過 `[[ -x ]]`，救不了沒有執行位元的情況；`mode` 成立，所以沒有量它們。
- **實測**（`scripts/experiments/inline_preseed.py`，`.local/experiments/results/inline-preseed-<label>.json`）：內嵌當下的 `deploy/preseed/qbittorrent/10-berth.sh`（`$` 寫成 `$$`），qbittorrent 照部署檔放在 `profiles: [qbittorrent]` 底下、旁邊一個沒有 profile 的服務代替 `berth`；每次全新的 CONFIG_ROOT，量首次啟動、`restart`、`up -d --force-recreate` 三個階段，另跑一次 `COMPOSE_PROFILES` 空的。

  | 環境 | Compose | Docker | qBittorrent image（`:latest` 當時） |
  | --- | --- | --- | --- |
  | 本機 Docker Desktop（Windows） | v5.3.1 | 29.6.2 | 5.2.3_v2.0.15-ls478 |
  | 同一台，官方獨立二進位（使用者 Unraid 同版） | v2.40.3 | 29.6.2 | 同上 |
  | 票 42 的 VM，rootless Docker | v5.3.1 | 29.7.1 | 5.2.4_v2.0.15-ls479 |

  三個環境結果相同：

  - `mode: 0555`：檔案 `root:root 0:0 555`，**內容與原檔 sha256 相同**（`$$` 都展開回 `$`）；log `10-berth.sh: executing...` → `[berth-preseed] added to …` → `exited 0`，沒有 tamper 警告；兩個鍵各一行；`/api/v2/app/version` 從 `BERTH_IP` 200、宿主經 published port 403、同網段另一個位址 403。`restart` 與 `--force-recreate` 之後都是 `already configured`、鍵仍各一行、狀態碼不變。
  - profile 關掉（`COMPOSE_PROFILES=`，使用者選了既有 qBittorrent）：`up -d` 回 0、沒有警告，只起沒有 profile 的那個服務；頂層 `configs` 沒人用不報錯。
  - 不寫 `mode`（對照組）：`root:root 444`，log 只有 `10-berth.sh: is not an executable file`，qBittorrent 照常起來但沒有白名單，`BERTH_IP` 也 403。**唯一的徵兆是那一行 log**。
  - 不是掛載：`docker inspect` 的 `Mounts` 只有 `/config`，Compose 在建立容器時把檔案寫進容器的檔案系統；`restart` 留著，重建時重新寫入。執行期不讀 compose 所在目錄，所以**推論** stack 目錄在 Unraid 隨身碟（vfat、不能執行）上也無妨——三個環境的 compose 目錄都不是 vfat，Unraid 上沒有實測（票 71 不碰 Unraid，使用者自己部署時會驗到）。
  - 不需要 `uid` / `gid`：預設就是 root（linuxserver 的 init 以 root 跑）。舊的 bind mount 在 Windows 上印的「write permissions for others」警告（票 56 Comments）也跟著消失。
- **坑**：`docker compose config` 的輸出會把 `$` 再轉義成 `$$`，拿它驗內容等於什麼都沒驗；從 compose 抽出腳本做測試時要把 `$$` 還原成 `$`。`mode` 寫 `0555` 這種前導 0 的八進位，v2.40.3 與 v5.3.1 都讀成 555。比 2.40.3 舊的 Compose（2.23.1 起有 `content`）沒有量。
- **決定的寫法**（票 71 照抄；`content` 底下是 `10-berth.sh` 全文，每個 `$` 寫成 `$$`）：

  ```yaml
  configs:
    qbittorrent-preseed:
      content: |
        #!/usr/bin/env bash
        # …10-berth.sh 全文，`${BERTH_IP:-}` 寫成 `$${BERTH_IP:-}`…

  services:
    qbittorrent:
      # …其餘不變，拿掉 `./preseed/qbittorrent:/custom-cont-init.d:ro` 那條掛載…
      configs:
        - source: qbittorrent-preseed
          target: /custom-cont-init.d/10-berth.sh
          mode: 0555
  ```

  漏掉 `mode` 不會報錯、只會讓 Berth 進不去，所以票 71 的閘門要守著 `mode` 帶執行位元。重量：`docs/development/experiments.md`。
- **票 71 照抄進部署檔之後的閘門**：`tests/unit/test_qbittorrent_preseed.py` 從 compose 抽出腳本（`$$` 還原）跑原有的行為斷言，並守著 `content` 裡沒有未轉義的 `$`、target 在 `/custom-cont-init.d/`、`mode` 帶執行位元；`tests/unit/test_deploy_mounts.py` 守著 compose 的宿主路徑沒有相對的。
