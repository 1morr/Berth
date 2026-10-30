# 部署只用 compose 檔加 `.env`；`.env` 只放 Berth 在容器裡看不到的主機端事實

使用者試跑時，套件的預設 port 與開發環境相撞：手改 compose 之後，深連結仍開到容器內的 8096，qBittorrent 的 WebUI 也回 401。決定：

- **`.env` 只放主機端事實**，也就是五個對外 port；Jellyfin 的 port 同時交給 Berth 推導深連結，qBittorrent 的 WebUI port 內外兩側一起換。
- **其餘設定不搬進 `.env`**：同一個值有兩個來源時必須選邊（Immich 設了 `IMMICH_CONFIG_FILE` 就把 UI 整個鎖住；Servarr 只把少數 key 開放成 `APP__SECTION__KEY` 環境變數）；Route 是動態的；`.env` 不放秘密（秘密在 DB，brief §16.2）；精靈「打開 8383 就能設定完」的價值要留著。
- **部署只用 compose 檔加 `.env`**（2026-10-09 使用者推翻「release zip 含 `preseed/`」）：貼進 Unraid Compose Manager 或任何資料夾就能 `up`，不下載 zip、不放額外檔案；preseed 腳本內嵌進 compose（brief §20.18）。2026-10-13 部分恢復：每一版的 Release 附上 `docker-compose.yml` 與 `example.env`（取自那一版的 tag），README 連 `releases/latest/download/<附件名>`，發版不必改連結（Immich 的慣例，§20.17）。使用者先前在意的是 zip，兩個純文字附件不在此限。

來源：brief §19 舊列「部署的 port 進 `.env`」「第四輪可用性審計的八項」E4、「部署檔改成最新 Release 的附件」（原文在 `docs/archive/m2.md`、`docs/archive/m4.md`）。
