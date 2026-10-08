# 70 — 原型：把 qBittorrent 的 preseed 腳本寫進 compose 檔

**Status:** done

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

- [x] 三個環境各有一次實跑紀錄：檔案權限、init log、`qBittorrent.conf` 兩個鍵、非白名單位址要密碼、重啟冪等
- [x] 選定的寫法在三個環境都成立；有任何一個不成立，寫明原因與替代方案，**停下來問使用者**再開 71
- [x] brief §20 新增一節（來源、指令、版本），實驗腳本在 `scripts/experiments/`，有使用說明
- [x] 本機與 VM 上這次起的容器與目錄都清掉；progress.md 記一行

## Comments

### 實跑（2026-10-09，`scripts/experiments/inline_preseed.py`）

內嵌的是當下的 `deploy/preseed/qbittorrent/10-berth.sh`（`$`→`$$`），每個變體全新的 CONFIG_ROOT；compose project /
network `berth-t70`、子網 10.70.0.0/16、WebUI port **7080**（協調者給的 78080 / 76881 超過 65535，取「7 開頭」的本意；
本機與 VM 事先確認沒被占）。qbittorrent 照部署檔放在 `profiles: [qbittorrent]` 底下，另有一個沒有 profile 的 `idle`
代替 `berth`。報告在 `.local/experiments/results/inline-preseed-{desktop,compose-2.40.3,vm-rootless}.json`（不進版控）。

| 環境 | Compose / Docker | image | `mode: 0555`（首次 / restart / recreate） | 不寫 `mode` | profile 關掉 |
| --- | --- | --- | --- | --- | --- |
| 本機 Docker Desktop | v5.3.1 / 29.6.2 | 5.2.3-ls478 | 三階段全部成立 | 444、`is not an executable file`、BERTH_IP 也 403 | `up -d` 回 0，只起 `idle` |
| 同機 v2.40.3 官方二進位（scratchpad，未換系統的） | v2.40.3 / 29.6.2 | 同上 | 三階段全部成立 | 同上 | 同上 |
| 票 42 的 VM，rootless | v5.3.1 / 29.7.1 | 5.2.4-ls479 | 三階段全部成立 | 同上 | 同上 |

「全部成立」逐項是：`root:root 0:0 555 regular file`；容器內 sha256 與原檔相同；log
`[custom-init] 10-berth.sh: executing...` → `[berth-preseed] added to /config/qBittorrent/qBittorrent.conf: WebUI\AuthSubnetWhitelistEnabled=true WebUI\AuthSubnetWhitelist=10.70.0.2/32`
→ `exited 0`（restart / recreate 是 `already configured, leaving … untouched`）；沒有 tamper 警告；兩個鍵各一行；
`/api/v2/app/version`：BERTH_IP 200、宿主經 published port 403、10.70.0.3 403。`docker inspect` 的 `Mounts` 只有
`/config`：Compose 把檔案寫進容器，不是 bind mount。結論與決定的寫法在 brief §20.18。

清理：每次跑完 `down --volumes` 並刪工作目錄；本機與 VM 上 `docker ps -a` / `docker network ls` 過濾 `berth-t70` 都是空的，
VM 的 `~/berth-t70` 已刪，本機 `.local/experiments/inline-preseed/` 空。v2.40.3 二進位在 session 的 scratchpad，不在 repo。

VM 上票 42 的四個容器在第一輪實跑中途（05:03:32 +08）被重建，labels 是 project `berth`、working_dir
`/home/cppt/berth-trial-42/berth`：那是票 42 自己的 compose，這支腳本只對 `berth-t70` 下指令，沒碰它。

### code-review（d3ca61f，Standards 與 Spec 兩軸 opus）已處理

- README 那一列接在檔尾、不在表格裡 → 移進表格（Standards）。
- 「容器都叫 `berth-t70`」不精確、「掛到」與 brief「不是掛載」矛盾 → 改寫（Standards）。
- `stages` 的第三欄沒人讀；宿主狀態碼是 int、另兩個是 str → 刪掉、`probe` 回 int（Standards）。
- `--keep` 配兩個變體時後一個會重建掉前一個 → `--keep` 只准配一個 `--variant`（Standards）。
- 部署檔的 qbittorrent 有 profile，profile 關掉時頂層 `configs` 沒人用會不會報錯沒量 → 加 `profile-off` 變體，三個環境重跑（Spec）。
- brief 沒說為什麼沒量 `bash …` / `exec bash` 兩種替代寫法、image 內 init 腳本沒附讀法、「隨身碟上也無妨」是推論 → 補上並標明（Spec）。
- 檔案不存在時 `split()[2]` 會 IndexError → 防住（Spec）。

### 未處理（判斷後留著）

- 前綴 `berth-t70` 不是既有實驗腳本的 `berth-exp-*`：協調者指定，為了與票 42 並行時好辨認；README 那一列寫了原因。
- `main` 不管結論都回 0：與其他實驗腳本一致，結論在報告裡。
- brief §19 E4 那列與 §20.17 還沒標推翻 / 取代：票 71 的「紀錄」一步明列要做，這張只在 §20.18 開頭寫推翻。
