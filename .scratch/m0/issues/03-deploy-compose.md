# 03 — deploy/：image 與 compose 套件

**Status:** ready-for-human

**Blocked by:** 02

**讀:** plan §9.1、§9.2、§9.6、§11.1（T0.7）；brief §16.1、§16.3、§20.7

## 做什麼

`deploy/` 下一份 `docker-compose.yml`，起 `berth` + qBittorrent + Jellyfin + Prowlarr，四者掛同一個 `DATA_ROOT` bind mount，網路固定子網 `172.28.0.0/16`，三個外部服務各掛在同名 profile 下、`berth` 永遠啟動。berth 用多階段 Dockerfile（node build → python slim、非 root、`PUID` / `PGID` 入口腳本）。qBittorrent 的 preseed 腳本走 linuxserver 的 `custom-cont-init.d`，只在 `qBittorrent.conf` 不存在時寫入免密白名單與 `ServerDomains`。另加 GHCR 發佈 workflow。

預置只放「沒有它 Berth 就進不去」的東西：temp path、save path、autoTMM、密碼一律不預置，留給精靈用 API 設定。

## 驗收

- [x] `docker compose up -d` 後四個容器健康，`:8383` 開得到 Berth，`:8080`、`:8096`、`:9696` 各自可達
- [x] 從 `COMPOSE_PROFILES` 拿掉 `jellyfin` 後只起三個容器，Berth 仍正常啟動
- [x] 在 berth 容器內 `curl -H 'Host: qbittorrent' http://qbittorrent:8080/api/v2/app/version` 免密回版本
- [x] preseed 腳本對已存在的 `qBittorrent.conf` 不做任何修改（重建容器兩次驗證）
- [x] berth 容器以非 root 執行，寫入 `/config` 與 `/data` 的檔案擁有者符合 `PUID` / `PGID`
- [x] image 壓縮後 < 400 MB
- [x] `.env.example` 含 `DATA_ROOT`、`CONFIG_ROOT`、`PUID`、`PGID`、`UMASK`、`TZ`、`COMPOSE_PROFILES`，附 Linux 與 Windows 兩種路徑寫法的註解，沒有任何秘密欄位
- [ ] GHCR workflow 在 tag 上 build 並推 image
- [x] README 補部署段：單一掛載根、不支援 exFAT、Windows 用一般 bind mount

## Comments

- 票 01 建的 README 只涵蓋開發指令。brief §16.1 要求 README 另外明列：硬鏈接前提
  （單一掛載、不可 exFAT、不可跨 btrfs 子卷 / ZFS dataset / mergerfs branch）、支援的宿主
  平台、qBittorrent 版本下限與必要設定、Jellyfin 需 MergeVersions 插件、TMDB 歸屬聲明與
  logo；brief §16.2 要求註明「API key 存在 DB，靠檔案權限保護，不做應用層加密」。
  這些屬於部署脈絡，在本票補進 README。

- 驗收條件 3 的字面指令跑不了：image 內沒有 curl（刻意不裝，省體積）。改用兩種等價方式
  驗證，都免密回 `v5.2.3`：berth 容器內 `python -c "…urlopen('http://qbittorrent:8080/api/v2/app/version')"`
  （這就是 adapter 之後真正走的路徑，Host 標頭同樣是 `qbittorrent`），以及同網段一次性
  容器 `docker run --network berth curlimages/curl -H 'Host: qbittorrent' …`。README 的部署
  疑難排解段記了 python 那條指令。
- **免密白名單縮成 berth 固定 IP 的 `/32`**，不是原本 plan 寫的整個網段。整段開放時
  Docker Desktop 把發佈 port 進來的流量 SNAT 成閘道位址（`172.28.0.1`，也在網段內），
  實測宿主 `curl http://localhost:8080/api/v2/app/version` 免密回 `v5.2.3` —— 等於 LAN 上
  任何人都進得去。改成 `172.28.0.2/32` 後：berth 200、宿主 403、同網段其他容器 403。
  plan §9.1、§9.2 與 brief §16.3、§20.7 已同輪回寫。
- preseed 改成「缺鍵才補」而非「檔案不存在才寫」：linuxserver 的 `init-qbittorrent-config`
  排在 `init-custom-files` 之前，已經把 `/defaults/qBittorrent.conf` 複製好，原條件永遠
  不成立；整份覆蓋還會掉 `LegalNotice\Accepted=true`（qbittorrent-nox 會卡住）。
- `WebUI\ServerDomains` 不預置：image 預設就是 `*`，Host 檢查本來就過得了，寫死成
  `qbittorrent` 反而讓使用者從 `localhost:8080` 進不了 WebUI。
- 最後一條驗收（GHCR workflow 在 tag 上推 image）沒辦法在本機驗證：repo 仍然沒有 remote，
  與票 01 的 CI 那條同樣狀況，所以 `Status` 停在 `ready-for-human`。compose 寫死的
  `ghcr.io/1morr/berth:latest` 假設 GitHub owner 是 `1morr`（workflow 用
  `github.repository_owner` 組同一個名字），建 remote 後要一起確認。
- code-review 的發現全部處理掉了，只有一項刻意不做：`BERTH_IP` 與 `BERTH_QBITTORRENT_CONF`
  沒有寫進 `deploy/.env.example`。前者由 compose 的錨點設定（使用者不該逐一改），後者只是
  測試用的 seam；`.env.example` 維持驗收列的那七個變數。
