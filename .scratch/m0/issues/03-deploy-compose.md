# 03 — deploy/：image 與 compose 套件

**Status:** ready-for-agent

**Blocked by:** 02

**讀:** plan §9.1、§9.2、§9.6、§11.1（T0.7）；brief §16.1、§16.3、§20.7

## 做什麼

`deploy/` 下一份 `docker-compose.yml`，起 `berth` + qBittorrent + Jellyfin + Prowlarr，四者掛同一個 `DATA_ROOT` bind mount，網路固定子網 `172.28.0.0/16`，三個外部服務各掛在同名 profile 下、`berth` 永遠啟動。berth 用多階段 Dockerfile（node build → python slim、非 root、`PUID` / `PGID` 入口腳本）。qBittorrent 的 preseed 腳本走 linuxserver 的 `custom-cont-init.d`，只在 `qBittorrent.conf` 不存在時寫入免密白名單與 `ServerDomains`。另加 GHCR 發佈 workflow。

預置只放「沒有它 Berth 就進不去」的東西：temp path、save path、autoTMM、密碼一律不預置，留給精靈用 API 設定。

## 驗收

- [ ] `docker compose up -d` 後四個容器健康，`:8383` 開得到 Berth，`:8080`、`:8096`、`:9696` 各自可達
- [ ] 從 `COMPOSE_PROFILES` 拿掉 `jellyfin` 後只起三個容器，Berth 仍正常啟動
- [ ] 在 berth 容器內 `curl -H 'Host: qbittorrent' http://qbittorrent:8080/api/v2/app/version` 免密回版本
- [ ] preseed 腳本對已存在的 `qBittorrent.conf` 不做任何修改（重建容器兩次驗證）
- [ ] berth 容器以非 root 執行，寫入 `/config` 與 `/data` 的檔案擁有者符合 `PUID` / `PGID`
- [ ] image 壓縮後 < 400 MB
- [ ] `.env.example` 含 `DATA_ROOT`、`CONFIG_ROOT`、`PUID`、`PGID`、`UMASK`、`TZ`、`COMPOSE_PROFILES`，附 Linux 與 Windows 兩種路徑寫法的註解，沒有任何秘密欄位
- [ ] GHCR workflow 在 tag 上 build 並推 image
- [ ] README 補部署段：單一掛載根、不支援 exFAT、Windows 用一般 bind mount

## Comments
