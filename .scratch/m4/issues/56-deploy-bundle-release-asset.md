# 56 — 部署檔變成 release 附件：下載一個 zip 就能部署

**Status:** ready-for-agent

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

- [ ] 產生 zip 的腳本與它的測試（雙向：缺預置腳本會紅、無關的檔名改動不紅）
- [ ] release workflow 在 tag 上附 zip；README〈版本與升級〉與 CHANGELOG `[Unreleased]` 說明新的取得方式
- [ ] 乾淨目錄照 zip 流程實跑到頁 2 綠，附指令輸出
- [ ] 全部檢查與 test 綠燈；progress.md 記一行
