# 42 — 原生 Linux 實跑部署與精靈

**Status:** needs-info

**Blocked by:** 使用者讓 VM 連得到 TMDB 與索引站（只剩 S1 入庫；VM 的 Clash Verge 節點不通，見 Comments）

**讀:** `docs/research/wizard-audit-2026-10-06.md`（環境限制 4、§C1、§C2、§3.2「compose 部署（原生 Linux / NAS）」、§3.3 阻擋項 3、改進清單 P0-3）；brief §16.1、§20.7、§20.14；票 16 的 Comments（`host-gateway` 沒實測）；README〈支援的宿主平台〉

## 為什麼

- 主要客群是 NAS，但目前只在 Windows Docker Desktop 跑過。下面這些都沒驗：`host-gateway`、PUID / PGID 與 `DATA_ROOT` 的擁有者、硬鏈接的檔案系統、Linux 上服務只監聽 `127.0.0.1` 的情況。

## 做什麼

1. 用 41 發出去的 image，照 README 在原生 Linux 上從頭跑。
2. S1：三個服務都選套件內，走完精靈，再送一筆公有領域的單走到入庫。
3. S2：既有 Jellyfin 與既有 qBittorrent 用 `host.docker.internal`（`host-gateway`），只多掛一條 `/data`（36 的做法）。
4. 找到的問題能在這張修的就修（compose、預置腳本、README）；修不了的開新票。
5. 結果寫成 `docs/research/` 下的實跑紀錄，結論與 Docker / 發行版版本摘進 brief §20.14（附腳本或指令）。

## 驗收

- [ ] 原生 Linux 上 S1 走完並入庫一部；附截圖或指令輸出（頁 1–3 走完、三條 Route 6/6；頁 4、5 起卡在 VM 的代理，沒入庫）
- [ ] 原生 Linux 上 S2 走完，`host.docker.internal` 連得到宿主上的既有服務；頁 3 6/6（**沒勾，等使用者決定**：這台是 rootless，`host.docker.internal` 連不到，改填區網 IP 後頁 3 兩條 6/6。rootful 的 `host-gateway` 只有票 55 在 Unraid 上的 `getent` 與 curl，沒有用它走過 S2。研究檔 §3.2、§5.1）
- [x] PUID / PGID 與 `DATA_ROOT` 擁有者不一致時的錯誤訊息實際看過一次，結論寫進研究檔（§4.2）
- [x] brief §20.14 與 README〈支援的宿主平台〉已改；progress.md 記一行（README〈Status〉與 `docs/guide/requirements.md`〈Host platforms〉）
- [x] 有改程式時：全部檢查（`pre-commit run --all-files`）、test 綠燈（沒改程式；部署檔註解與文件，照樣跑過）

## Comments

- **2026-10-09 實跑**（`docs/research/linux-trial-2026-10-09.md`）：機器是 VM `ubuntu-devbox`（`cppt-dev`，192.168.50.99），Ubuntu 26.04、Docker 29.7.1 **rootless**、Compose v5.3.1、ext4；`sudo -n true` 要密碼，全程用 rootless docker。
- **沒做完的：S1 入庫**。VM 上的 Clash Verge（mihomo TUN）選的節點 04:45–05:22 整段不通，TMDB、索引站、`lscr.io`、`indexers.prowlarr.com` 全部 TLS 失敗（從 Windows 主機打都正常）。改節點或關 TUN 是使用者的設定，沒有動。**接手的人**：使用者讓 VM 連得到 `api.themoviedb.org` 之後，`cd ~/berth-trial-42/berth && docker compose up -d`（S2 那一套要先 `docker compose down`，一台只跑一套），以 `owner` 登入（密碼在 VM 的 `~/berth-trial-42/.trial/pw`），從頁 4 繼續：推薦站、頁 5 TMDB（key 照票 55 的做法經 ssh stdin）、完成、送一部公有領域電影、看入庫的 inode 與擁有者（`PUID=1000` 那一套，宿主上應是 100999）。補完把第一條勾掉、Status 改 done。
- 新開的票：**72**（精靈的 `host.docker.internal` 提示與 `berth_cannot_write` 補法加 rootless 的說法）、**73**（頁 4 推薦站全部不在 Prowlarr 時不說原因）。
- **原本的 Blocked by**（2026-10-09 移過來）：41；**58（0.2.0 公開 beta：照新的英文 README 與 release zip 從零跑，2026-10-08 改）**；**使用者提供一台原生 Linux 機器**（開工前先問：主機、Docker 版本、能不能用 `sudo`、`DATA_ROOT` 放哪個檔案系統）。**2026-10-08**：機器是使用者電腦上 VMware Workstation 的 Linux VM（brief §19「第四輪可用性審計的八項」E8）；第四輪審計建議等 0.2.0 與新的取得方式（E4、E5、E7）之後再跑，讓這一輪同時驗新使用者實際會走的路
- **code-review**（兩軸 opus，`d3ca61f` 之後的 working tree）：已處理——progress.md、證據檔（chown 補救、Prowlarr 與 Berth 在 `PUID=0` 下的行程、網路、頁 4、S2 媒體庫路徑）、探測腳本留進 `scripts/experiments/rootless_host_probe.sh`、README 與 guide 只說「頁 1–3」、CHANGELOG 自相矛盾的一句、brief 新條目補來源 URL、S2 那一格改回沒勾、Blocked by 的歷史移到這裡。**沒處理**：rootless 的說法分散在 8 處（README 兩份、`.env.example`、compose、guide 兩份、brief、CHANGELOG）——部署檔的註解是拿到 compose 的人唯一看得到的說明，guide 是要點進去的人看的，各留一句結論；票 72 改精靈文案時同步一次。
- **全部檢查**（文件定稿後重跑）：`uv run pre-commit run --all-files` 十二個 hook 全 Passed（trailing whitespace、end of files、merge conflicts、yaml、toml、mixed line ending、ruff check、ruff format、mypy、import-linter、prettier、eslint）；`uv run pytest -q` → `3678 passed, 24 deselected in 1075.46s`；之後改過的文件再跑 `-k "readme or deploy or preseed or compose or experiment"` → `65 passed`。
