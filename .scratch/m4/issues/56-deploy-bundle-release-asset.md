# 56 — 部署檔變成 release 附件：下載一個 zip 就能部署

**Status:** done

**Blocked by:** None — can start immediately（與 55 不衝突，可並行）

**讀:** `docs/research/usability-audit-2026-10-07.md` §2 E4、§7、§8 P0-1、P2-14；`docs/research/usability-audit-2026-10-07/notes/r2-docs-and-research.md` §1.2 S1、§1.5〈取得檔案：兩個具體方案〉、§1.6；README〈版本與升級〉；brief §19「第四輪可用性審計的八項」E4

## 為什麼

- 現在的 README 叫人 `cd deploy`，卻沒說 `deploy/` 從哪裡來（審計 P0-1）。
- 只抓 compose 一個檔不夠：缺了預置腳本那個目錄，套件內 qBittorrent 會讓 Berth 進不去。
- 使用者拍板 E4：照 Immich 的做法，把部署需要的檔案打成 release 附件，不叫人 clone、不內嵌腳本。

## 做什麼

1. 每次發版，release 上多一個附件：一個 zip，內容是 compose 檔、`.env.example`、預置腳本目錄，解壓即可用；檔名帶版本。另外附一個固定名稱的「最新版」下載連結（GitHub `releases/latest/download/…`），README 才能寫死。
2. zip 的內容由一支腳本產生，CI 與本機用同一支；測試守住「zip 裡一定有預置腳本、compose 引用的每個相對路徑都在 zip 裡」（造一個缺檔的版本證明會紅）。
3. 預發佈 tag（`-rc`）也產生附件，但不動 `latest`，照 README〈版本與升級〉現有規則。
4. 「同一台主機不能並存兩套」（P2-14）不改 compose，在 zip 內的 `.env.example` 註解說明一台一套。
5. **實跑**：在乾淨目錄下照「下載 zip → 解壓 → `cp .env.example .env` → `docker compose up -d`」走一次。用本機產生的 zip，不必真的發版；頁 2 套件內 qBittorrent 能連上。

## 驗收

- [x] 產生 zip 的腳本與它的測試（雙向：缺預置腳本會紅、無關的檔名改動不紅）
- [x] release workflow 在 tag 上附 zip；README〈版本與升級〉與 CHANGELOG `[Unreleased]` 說明新的取得方式
- [x] 乾淨目錄照 zip 流程實跑到頁 2 綠，附指令輸出
- [x] 全部檢查與 test 綠燈；progress.md 記一行

## Comments

### 實跑（2026-10-08，Windows Docker Desktop）

本機產生的 zip，乾淨目錄（repo 外的 scratchpad），不發版：

```
$ uv run python scripts/deploy_bundle.py v0.2.0-t56 --out dist
dist/berth-deploy-0.2.0-t56.zip            # 另有同內容的 dist/berth-deploy.zip
$ cp dist/berth-deploy.zip t56/ && cd t56 && unzip berth-deploy.zip && cd berth && cp .env.example .env
  inflating: berth/.env.example
  inflating: berth/docker-compose.yml
  inflating: berth/preseed/qbittorrent/10-berth.sh      # 0755
$ docker compose up -d && docker compose ps
berth-t56              Up 22 seconds (healthy)
berth-t56-jellyfin     Up 22 seconds (healthy)
berth-t56-prowlarr     Up 22 seconds (healthy)
berth-t56-qbittorrent  Up 22 seconds (healthy)
$ docker compose logs qbittorrent
[custom-init] 10-berth.sh: executing...
[berth-preseed] added to /config/qBittorrent/qBittorrent.conf: WebUI\AuthSubnetWhitelistEnabled=true WebUI\AuthSubnetWhitelist=10.232.0.2/32
[custom-init] 10-berth.sh: exited 0
```

精靈頁 1 套件內 Jellyfin 建管理員 → 頁 2 選套件內 qBittorrent：「qBittorrent 連上了：連線測試通過」、
v5.2.3 · Web API 2.15.1、WebUI 登入已完成，BTH 1、BTH 2 綠（playwright 截圖 `.playwright-mcp/t56-page2-green.png`，
不進版控）。結束後 `docker compose down`。

**為了與本機其他票的 stack 並存而偏離「照抄」的地方**（zip 裡的檔案一字未改）：`.env` 的五個 port 改成 2xxxx、
加 `COMPOSE_PROJECT_NAME=berth-t56`；旁邊放一份 `docker-compose.override.yml` 換容器名、網路名與子網
（`10.232.0.0/16`，berth 固定 IP 跟著換）——這正是 P2-14「一台一套」；`berth` 換成這個 worktree build 的
`berth:t56`（GHCR 的 `:latest` 還是 0.1.0，票 58 才發新版）。

### code-review（b10c9c7...acf4ac9）已處理

- 「zip 裡要有 compose 與 `.env.example`」那一條補了變異測試（Standards）。
- release 改成 `gh release create <tag> dist/*.zip`：gh 帶附件時先建草稿、傳完才發佈，`latest/download/` 不會有
  一段 404（Spec；查證寫進 brief §20.17）。
- README「同一台還跑著另一套 Berth 就改 port」與 `.env.example` 同一句和「一台一套」矛盾，改掉；README 面向
  使用者的 `deploy/...` 路徑改成部署套件的（Spec、Standards）。
- 可執行位元的測試不再寫死 `10-berth.sh`，改成 `preseed/` 底下每個檔案（Spec）。
- 版本的 `v` 只在腳本剝一次；`ZipFile` 多設的壓縮法拿掉；brief §20.17 補 Immich 的來源、拿掉沒用到的 `--latest=false`。

### 未處理（判斷後留著）

- `DEPLOY` 在 `scripts/deploy_bundle.py` 與 `tests/unit/test_deploy_ports.py` 各算一次；`berth-deploy` 前綴在
  `LATEST_NAME` 與 `bundle_name()` 各寫一次：同檔或相鄰，抽出來不比現在清楚。
- README 寫 `uv run python scripts/deploy_bundle.py`、workflow 寫 `uv run --no-project ...`：同一支腳本，CI 為了
  不 sync 整個專案；本機已經 sync 過，兩種都對。
- release notes 是英文一句加 CHANGELOG 連結（字串常量，全域規則允許）；內容在 CHANGELOG。
- release 已存在時（重跑、或有人先在 UI 手動建了 `-rc` 的 release）只重傳附件，不去改它的 prerelease 標記。
- 本機 `deploy/preseed/` 裡沒進版控的檔案也會被打進 zip；CI 是乾淨 checkout，不影響發版。
- 非 `.sh` 檔是 644 沒有反向斷言：不是規則，只是預設。
- **zip 裡的 compose 永遠拉 `:latest`**，`-rc` 的 zip 也是（拉到的是最新正式版，不是那個 rc）。票面沒要求；
  票 58 若要先發 rc 驗證，記得手動把 image 換成 `:<版本>`。
- 解壓出來的檔案時間是 1980-01-01（為了輸出可重現）。
- linuxserver 對 `/custom-cont-init.d` 印「write permissions for others」警告：Windows bind mount 的權限，repo 裡
  原本的 `deploy/` 也一樣（本機另一套 `berth-qbittorrent` 也印），腳本照樣執行。Unraid 的情況看票 55。
- `releases/latest/download/berth-deploy.zip` 在票 58 發 0.2.0 之前是 404（目前沒有任何 release 帶這個附件）。
