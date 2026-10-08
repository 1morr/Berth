# 70 — 原型：把 qBittorrent 的 preseed 腳本寫進 compose 檔

**Status:** ready-for-agent

**Blocked by:** None — can start immediately（只在本機與 VM 上跑，不碰 Unraid；與 42 不衝突）

**讀:** brief §19「第四輪可用性審計的八項」E4、§20.17；票 56、58 的 Comments；`docs/guide/requirements.md`〈Unraid〉；部署用 compose 檔與它掛載的 qBittorrent preseed 腳本（腳本開頭的註解說明它為什麼存在）

## 為什麼

- 使用者拍板（2026-10-09）：**部署只要 compose 檔加 `.env`，不下載 zip、不放任何額外檔案**。Release 頁保留，但只放說明、不再附 zip。這推翻 E4「部署檔改成 release 附件，不內嵌 preseed」。
- 使用者實際會在 Unraid 的 Compose Manager 裡直接貼 compose、改 `.env`。stack 目錄在隨身碟（`/boot/config/plugins/compose.manager/projects/<名稱>/`）上：
  - compose 裡唯一的相對路徑 `./preseed/qbittorrent` 會掛到一個不存在的空目錄；
  - 白名單沒寫進去，套件內的 qBittorrent 就不讓 Berth 登入（4.6.1 之後隨機密碼只印在 log）。
- 候選做法是 Compose 頂層 `configs:` 的 `content:`：把腳本內容寫在 compose 裡，掛到 `/custom-cont-init.d/10-berth.sh`。Docker 文件寫明：
  - `content` 從 Compose 2.23.1 起支援；
  - 預設擁有者是容器的執行使用者、權限 0444，可在服務的 `configs` 長語法裡覆寫；
  - `content` 會做變數展開，所以腳本裡的 `$` 要寫成 `$$`。
- 文件沒說清楚、要實測的：
  - 不用 swarm 時，`mode` / `uid` / `gid` 有沒有效；
  - linuxserver 的 init 對 `/custom-cont-init.d` 的擁有者與權限有檢查，它認不認這種掛法；
  - 不同 Compose 版本行為一不一致。

## 做什麼

1. 寫一份最小的 compose：只有套件內 qBittorrent（與 Berth 部署檔同一個 image tag）加上 `configs.content` 內嵌的 preseed 腳本，`BERTH_IP` 照部署檔的寫法給。
2. 在三個環境各跑一次，每次都是全新的 `CONFIG_ROOT`：
   - 本機 Docker Desktop 的 Compose v5.3；
   - Compose **v2.40.3**：與使用者 Unraid 同版，下載官方二進位放在 repo 外，不換掉系統的；
   - 42 那台 VM 的 rootless Docker（Compose v5.3.1，`ssh -F /dev/null -i ~/.ssh/cppt-dev-ed25519 cppt@cppt-dev.local`，不用 sudo）。
3. 每次記錄：
   - 掛進去的檔案的擁有者、權限、內容（`$$` 展開成 `$` 了沒）；
   - linuxserver init 的 log 有沒有執行它、有沒有警告；
   - `qBittorrent.conf` 有沒有那兩個鍵；
   - 從 `BERTH_IP` 以外的位址打 API 仍要密碼；
   - 重啟容器第二次不重複加鍵（冪等）。
4. 不能用 `mode` 時，換別的寫法再量。例如入口改成 `bash /custom-cont-init.d/...`，或 `content` 只放一行 `exec bash` 呼叫。每個寫法都記成功或失敗與原因。
5. 結論寫回 brief §20（新的一節，附官方文件連結與實測指令）。實驗腳本留在 `scripts/experiments/`（plan §10），下次換 Compose 或 linuxserver 版本可以重量。
6. 結論附一段**決定用的 compose 片段**（只留 `configs` 宣告與服務掛法），給票 71 照抄。

## 驗收

- [ ] 三個環境各有一次實跑紀錄：檔案權限、init log、`qBittorrent.conf` 兩個鍵、非白名單位址要密碼、重啟冪等
- [ ] 選定的寫法在三個環境都成立；有任何一個不成立，寫明原因與替代方案，**停下來問使用者**再開 71
- [ ] brief §20 新增一節（來源、指令、版本），實驗腳本在 `scripts/experiments/`，有使用說明
- [ ] 本機與 VM 上這次起的容器與目錄都清掉；progress.md 記一行
