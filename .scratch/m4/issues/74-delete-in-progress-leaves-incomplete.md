# 74 — 刪除還在下載的單：incomplete 目錄裡的檔案留著，畫面說空出 0

**Status:** ready-for-agent

**Blocked by:** None — can start immediately

**讀:** `docs/research/linux-trial-2026-10-09.md` §3.1（S1 送單之後）與 [`s1-download.txt`](../../../docs/research/linux-trial-2026-10-09/s1-download.txt)；`berth/services/deletion.py` 開頭的模組說明與 `delete_job`；brief §9.2（刪除範圍）、§16.4 物件表；plan §3.1 最後一列

## 為什麼

票 42 在 VM 上取消一筆下載到 19.8% 的單：`DELETE /api/jobs/{hash}?remove_torrent=true&delete_files=true` 回 200、`{"links":0,"sources":0,"torrent":true,"purged":false,"freed":0}`，Berth 的 log 有一次 `POST /api/v2/torrents/delete`。torrent 從 qBittorrent 移除了，但 `DATA_ROOT/torrent/incomplete/movies/<種子名>/<檔名>.mkv` 留著，表觀大小 970,293,554 位元組（torrent 970,294,506）。使用者勾了刪檔，畫面說空出 0，磁碟上卻多一份沒有任何東西管的半成品。

原因在設計裡：`deletion.py` 的「刪除檔案」只刪 **complete** 根目錄底下、Berth 認得的來源（`paths.sources`，`_remove_all(..., roots=[paths.complete_root])`），`client.delete_torrent(job.hash, delete_files=False)` 固定不叫 qBittorrent 刪。還在下載的 torrent，資料在 incomplete 目錄（每個 `berth-*` 分類自帶的 incomplete 資料夾），兩條路都碰不到。

**失效條件**：一筆還沒完成的 Job（資料仍在 `/data/torrent/incomplete/<slug>/` 底下）以 `remove_torrent=true&delete_files=true` 刪除 → incomplete 目錄底下那一包留著，`freed` 是 0。

## 做什麼

1. 刪檔的範圍包含這筆 Job 在 incomplete 目錄底下的那一包（只限那一個 torrent 的內容路徑，仍然逐檔刪、在 incomplete 根目錄之內，與 complete 那一側同一套安全檢查）。
2. 刪除前的估算（`estimate_deletion`）與刪除對話框照實算進這一包的空間。
3. 已經 `client_removed`、不知道 incomplete 內容路徑的那一種照舊，不猜路徑。

## 驗收

- [ ] services 測試先紅：下載中的 Job 勾刪檔，incomplete 底下那一包被刪、`freed` 算得出；complete 那一側的既有測試不變
- [ ] 估算與對話框的數字包含 incomplete 那一包（vitest 或 API 測試）
- [ ] 實跑：本機 Docker Desktop 送一筆、下載中取消並刪檔，`find` 找不到殘留，附指令輸出
- [ ] 全部檢查（`pre-commit run --all-files`）、test 綠燈
