# 74 — 刪除還在下載的單：incomplete 目錄裡的檔案留著，畫面說空出 0

**Status:** done

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

- [x] services 測試先紅：下載中的 Job 勾刪檔，incomplete 底下那一包被刪、`freed` 算得出；complete 那一側的既有測試不變
- [x] 估算與對話框的數字包含 incomplete 那一包（vitest 或 API 測試）
- [x] 實跑：本機 Docker Desktop 送一筆、下載中取消並刪檔，`find` 找不到殘留，附指令輸出
- [x] 全部檢查（`pre-commit run --all-files`）、test 綠燈

## 實跑（2026-10-13）

本機 Docker Desktop，e2e 那一套 compose（`tests/e2e/stack.py`，image 從這個分支 build；qBittorrent 5.2.4）。精靈照 e2e 走完、
三包送單之後，在 The Bear S03 那一包的下載路徑放進位元組（最大的一個檔砍半）、recheck；沒有 peer，停在 `stalledDL`。
暫時的測試模組跑完就刪了，沒有 commit。

```
$ qBittorrent torrents/info?hashes=02cd8443d18e2c59c75e0e89e48f998fb5edfc2c
{"state": "stalledDL", "progress": 0, "save_path": "/data/torrent/complete/tv", "download_path": "/data/torrent/incomplete/tv", "content_path": "/data/torrent/incomplete/tv/The.Bear.S03.COMPLETE.1080p.HULU.WEB.H264-SuccessfulCrab[TGx]"}

$ GET /api/jobs/02cd8443d18e2c59c75e0e89e48f998fb5edfc2c
{"state": "metadata_ready", "progress": 0.0, "save_path": "/data/torrent/complete/tv", "content_path": "/data/torrent/incomplete/tv/The.Bear.S03.COMPLETE.1080p.HULU.WEB.H264-SuccessfulCrab[TGx]"}

$ find /data/torrent -type f (before)
/data/torrent/incomplete/tv/The.Bear.S03.COMPLETE.1080p.HULU.WEB.H264-SuccessfulCrab[TGx]/The.Bear.S03E10.1080p.WEB.H264-SuccessfulCrab.mkv
…（同一個目錄，共 10 集 + 2 個 .txt，12 個檔案）

$ GET /api/jobs/02cd8443d18e2c59c75e0e89e48f998fb5edfc2c/deletion
{"links": 0, "links_missing": 0, "sources": 12, "sources_missing": 0, "reclaimable": 97455, "held": 0}

$ DELETE /api/jobs/02cd8443d18e2c59c75e0e89e48f998fb5edfc2c?remove_torrent=true&delete_files=true
200 {"links":0,"sources":12,"torrent":true,"purged":false,"freed":97455,"unmanaged":[]}

$ qBittorrent torrents/info?hashes=02cd8443d18e2c59c75e0e89e48f998fb5edfc2c
[]

$ find /data/torrent (after)
/data/torrent
/data/torrent/complete
/data/torrent/complete/anime
/data/torrent/complete/movies
/data/torrent/complete/tv
/data/torrent/incomplete
/data/torrent/incomplete/anime
/data/torrent/incomplete/movies
```

進度是 0 而不是下到一半：e2e 的種子影片很小，一包只有一兩個 piece，砍半之後整包都校驗不過。資料在 incomplete、torrent 在
下載中，正是票面的失效條件。Berth 那一側停在 `metadata_ready`（進度 0 不算 `downloading`）。

## Comments

code-review（2026-10-13）沒處理的兩條：

- **空出多少用的是表觀大小（`st_size`）**：qBittorrent 預設不預先配置，下到一半的檔是 sparse 檔——票 42 那一筆表觀 970 MB、
  實際只下了約 192 MB，`freed` 與估算會多報。要改就是 `_measure` 換成配置的區塊（`st_blocks`），而那會改到每一種估算
  （complete 那一側也會變成以區塊取整），Windows 上沒有 `st_blocks`。超出這張票，要不要做留給使用者拍板。
- **空掉的目錄收到根目錄為止**：實跑裡刪完之後 `incomplete/tv`（那條 Route 分類的未完成目錄）也一起被收掉了。complete 那一側
  本來就這樣收（`complete/<slug>` 空了也會收），所以照同一套；Route 檢查的第一步會先 `ensure_directory` 兩個目錄、qBittorrent
  下載時也自己建，不會報紅。若要留著分類目錄，兩側一起改 `prune_empty_parents` 的終點。
