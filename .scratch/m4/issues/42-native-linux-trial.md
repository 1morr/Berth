# 42 — 原生 Linux 實跑部署與精靈

**Status:** needs-info

**Blocked by:** 41；**58（0.2.0 公開 beta：照新的英文 README 與 release zip 從零跑，2026-10-08 改）**；**使用者提供一台原生 Linux 機器**（開工前先問：主機、Docker 版本、能不能用 `sudo`、`DATA_ROOT` 放哪個檔案系統）。**2026-10-08**：機器是使用者電腦上 VMware Workstation 的 Linux VM（brief §19「第四輪可用性審計的八項」E8）；第四輪審計建議等 0.2.0 與新的取得方式（E4、E5、E7）之後再跑，讓這一輪同時驗新使用者實際會走的路

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

- [ ] 原生 Linux 上 S1 走完並入庫一部；附截圖或指令輸出
- [ ] 原生 Linux 上 S2 走完，`host.docker.internal` 連得到宿主上的既有服務；頁 3 6/6
- [ ] PUID / PGID 與 `DATA_ROOT` 擁有者不一致時的錯誤訊息實際看過一次，結論寫進研究檔
- [ ] brief §20.14 與 README〈支援的宿主平台〉已改；progress.md 記一行
- [ ] 有改程式時：全部檢查（`pre-commit run --all-files`）、test 綠燈
