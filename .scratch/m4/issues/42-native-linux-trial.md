# 42 — 原生 Linux 實跑部署與精靈

**Status:** done

**Blocked by:** 41、58（完成）；機器由使用者提供（VMware 上的 Ubuntu VM，見 Comments）

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

- [x] rootless 原生 Linux 上 S1 精靈頁 1–6 走完、送單成功，附截圖（研究檔 §3.1、s1-01–s1-10）；入庫那一段的端到端由票 55（Unraid：[`unraid-trial-2026-10-08.md` §3.1](../../../docs/research/unraid-trial-2026-10-08.md#31-時間線)）與票 58（Docker Desktop：[票 58](58-release-0-2-0-public-beta.md) 的乾淨環境實跑）實證；VM 上的下載在 40 分鐘內只到 19.8%，看到的證據照實記在 [`s1-download.txt`](../../../docs/research/linux-trial-2026-10-09/s1-download.txt)，原因不明（2026-10-09 改寫，原文與理由見 Comments）
- [x] 原生 Linux 上 S2 走完、頁 3 6/6；既有服務的位址：**rootful** 以 `host.docker.internal`（`host-gateway`）連得到宿主上的既有服務（引用票 55 在 Unraid 7.1.4 上的實測：[`unraid-trial-2026-10-08.md` §5.2](../../../docs/research/unraid-trial-2026-10-08.md#52-hostdockerinternal)）；**rootless** 不通、要填宿主的區網 IP（本票實測，研究檔 §3.2、§5.1），精靈文案交給票 72（2026-10-09 改寫，原文與理由見 Comments）
- [x] PUID / PGID 與 `DATA_ROOT` 擁有者不一致時的錯誤訊息實際看過一次，結論寫進研究檔（§4.2）
- [x] brief §20.14 與 README〈支援的宿主平台〉已改；progress.md 記一行（README〈Status〉與 `docs/guide/requirements.md`〈Host platforms〉）
- [x] 有改程式時：全部檢查（`pre-commit run --all-files`）、test 綠燈（沒改程式；部署檔註解與文件，照樣跑過）

## Comments

- **2026-10-09 實跑**（`docs/research/linux-trial-2026-10-09.md`）：機器是 VM `ubuntu-devbox`（`cppt-dev`，192.168.50.99），Ubuntu 26.04、Docker 29.7.1 **rootless**、Compose v5.3.1、ext4；`sudo -n true` 要密碼，全程用 rootless docker。
- **S1 中途停過一次**：VM 上的 Clash Verge（mihomo TUN）選的節點 04:45–05:22 整段不通，TMDB、索引站、`lscr.io`、`indexers.prowlarr.com` 全部 TLS 失敗（從 Windows 主機打都正常），停在頁 4。改節點是使用者的設定，沒有動；使用者換了節點之後 05:50 確認通了，從頁 4 接著做完。
- **驗收第 1 條改寫**（2026-10-09，使用者經協調者決定不等入庫）：原文「原生 Linux 上 S1 走完並入庫一部；附截圖或指令輸出」。精靈頁 1–6 走完，05:58:02 送出《Night of the Living Dead》(1968) 925 MB；06:00 拿到 metadata、開始下載，到 06:40 只到 19.8%：tracker 報 61 個種子，實際連上 3 個 peer（μTP），往外連 peer 有 `connection refused` 與 `i/o timeout`。照這個速度還要約兩小時（qBittorrent 的 `eta 6878` 秒）。為什麼這麼慢沒有查清楚——rootless 的 port 轉送、slirp4netns、VM 的 NAT 與代理都在路上，沒有逐一排除，所以不寫原因。入庫那一段（下載完成 → 解析 → 硬鏈接 → Jellyfin 反查）與宿主平台無關的部分已由票 55（Unraid，原生 Linux rootful）與票 58（Windows Docker Desktop）實證，硬鏈接本身在這台的 Route 檢查裡也做過（`hardlink` 6/6 的最後一項）。改寫後：rootless 上精靈頁 1–6 走完、送單成功，入庫引用 55 與 58，下載的證據照實記錄。06:40:48 在 Berth 裡刪掉這一筆（`remove_torrent` + `delete_files`）；incomplete 目錄裡的檔案留著，開**票 74**，那一份手動刪了。
- 新開的票：**72**（精靈的 `host.docker.internal` 提示與 `berth_cannot_write` 補法加 rootless 的說法）、**73**（頁 4 推薦站全部不在 Prowlarr 時不說原因；網路通了之後主鍵就回來，證實了它的失效條件）、**74**（刪除還在下載的單，incomplete 目錄的檔案留著）。
- **原本的 Blocked by**（2026-10-09 移過來）：41；**58（0.2.0 公開 beta：照新的英文 README 與 release zip 從零跑，2026-10-08 改）**；**使用者提供一台原生 Linux 機器**（開工前先問：主機、Docker 版本、能不能用 `sudo`、`DATA_ROOT` 放哪個檔案系統）。**2026-10-08**：機器是使用者電腦上 VMware Workstation 的 Linux VM（brief §19「第四輪可用性審計的八項」E8）；第四輪審計建議等 0.2.0 與新的取得方式（E4、E5、E7）之後再跑，讓這一輪同時驗新使用者實際會走的路
- **code-review**（兩軸 opus，`d3ca61f` 之後的 working tree）：已處理——progress.md、證據檔（chown 補救、Prowlarr 與 Berth 在 `PUID=0` 下的行程、網路、頁 4、S2 媒體庫路徑）、探測腳本留進 `scripts/experiments/rootless_host_probe.sh`、README 與 guide 只說「頁 1–3」、CHANGELOG 自相矛盾的一句、brief 新條目補來源 URL、S2 那一格改回沒勾、Blocked by 的歷史移到這裡。**沒處理**：rootless 的說法分散在 8 處（README 兩份、`.env.example`、compose、guide 兩份、brief、CHANGELOG）——部署檔的註解是拿到 compose 的人唯一看得到的說明，guide 是要點進去的人看的，各留一句結論；票 72 改精靈文案時同步一次。
- **全部檢查**（文件定稿後重跑）：`uv run pre-commit run --all-files` 十二個 hook 全 Passed（trailing whitespace、end of files、merge conflicts、yaml、toml、mixed line ending、ruff check、ruff format、mypy、import-linter、prettier、eslint）；`uv run pytest -q` → `3678 passed, 24 deselected in 1075.46s`；之後改過的文件再跑 `-k "readme or deploy or preseed or compose or experiment"` → `65 passed`。
- **驗收第 2 條改寫**（2026-10-09，使用者經協調者決定）：原文「原生 Linux 上 S2 走完，`host.docker.internal` 連得到宿主上的既有服務；頁 3 6/6」。這台 VM 是 rootless Docker，`host.docker.internal` 解成 RootlessKit 命名空間裡的 `172.17.0.1`，連不到宿主上任何東西，照原文不可能成立；手邊沒有能免密 sudo 的 rootful Linux。所以拆成兩半：rootful 的那一半引用票 55 在 Unraid（原生 Linux、rootful Docker 27.5.1）上的實測——`getent` 解成 docker0 的 `172.17.0.1`、打宿主上既有的 qBittorrent / Emby 都連到；rootless 的那一半照實記「不通、要填區網 IP」，並由票 72 改精靈文案。S2 的頁 3 6/6 是在 rootless 上以區網 IP 做到的。
- **收尾的全部檢查**（S1 送單、驗收改寫之後）：`uv run pre-commit run --all-files` 全 Passed；這一輪只改文件與新票，沒有動程式，所以沒有重跑完整的 pytest（上一輪是 `3678 passed`），文件相關的 `-k "readme or deploy or preseed or compose or experiment"` → `65 passed`。
