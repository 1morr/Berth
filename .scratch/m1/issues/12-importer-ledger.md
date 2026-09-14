# 12 — importer、ledger 與 Jellyfin 反查

**Status:** done

**Blocked by:** 11

**讀:** plan §3.1（importing 段）、§3.2（importer / jellyfin_resolver）、§3.3、§8.2、§8.6、
§11.2（T1.6 後半）；brief §4.4、§5.3、§7.7、§20.1

## 做什麼

**M1 的驗收就在這一票**：Plan 套用 → 硬鏈接進 library → 寫 ledger → 通知 Jellyfin → 反查 item id
→ 觸發 MergeVersions。做完之後，一部美劇一季、一部動漫一季、一部電影三者不經人工就入庫，並在
Jellyfin 正確顯示。

硬鏈接的方向照 brief §4.4：來源在 complete，目標在 Route 的 `target_path` 之下。寫入 library 的
路徑一律要在某個 Route 的 `target_path` 底下，否則 fs adapter 丟 `PathEscapeError`（plan §8.6）。

Jellyfin 反查用 brief §20.1 的兩段查詢，**不要用 `parentId=<seriesId>` 或 `/Shows/{id}/Episodes`**
（10.11 第一次掃描後兩者都回 0，plan §8.2）。

## 驗收

- [x] `ledger` 表與 migration，`target_path` unique
- [x] `importer` 事件驅動 + 每 60s 掃 `importing`；逐 item：建目錄 → `link()` → 寫 ledger → event；
      一次只處理一個 job
- [x] 目標已存在且 inode 相同 → 視為已完成並補上缺的 ledger；inode 不同 → item 標
      `target_unmanaged` 並進 review（plan §3.3；原文 `target_exists_foreign`，code-review 依
      CONTEXT.md 的 Unmanaged 改名）
- [x] 任一 item 失敗且不可跳過 → `import_failed`；重試時已完成的 item 跳過
- [x] 全部套用後 `POST /Library/Media/Updated` 通知 Jellyfin；失敗只記 event，不阻擋 `imported`
- [x] `jellyfin_resolver` 以 brief §20.1 的兩段查詢找 item id，重試 30s → 2m → 10m → 1h 共 6 次；
      耗盡記 event（`issues` 表在 M2）
- [x] MergeVersions 以 `settings.services.jellyfin` 存下的任務 Id 觸發；找不到只記 event
- [x] 硬鏈接後來源與目標的 inode 相同（測試實際比對，不是只看回傳值）
- [x] `EXDEV` 等 `OSError` 往上丟並帶 `errno`，訊息說得出是哪個掛載的問題
- [x] 寫入 library 的路徑不在任何 Route 的 `target_path` 之下時丟 `PathEscapeError`（有測試）
- [x] event 的去重規則（`(job_hash, type, payload hash)` 同一分鐘內）有測試，重啟不重複「completed」
- [x] **一部美劇一季、一部動漫一季、一部電影三者不經人工入庫，並在真的 Jellyfin 顯示正確的
      季集、標題與海報**（brief §17 M1 驗收），附證據
- [x] lint / type / test 全綠並貼指令輸出

## 驗證

```
$ uv run ruff check berth tests scripts && uv run ruff format --check berth tests scripts
All checks passed!
192 files already formatted

$ uv run mypy
Success: no issues found in 188 source files

$ uv run lint-imports
Contracts: 6 kept, 0 broken.

$ uv run pytest -q
11 failed, 1199 passed in 211.22s (0:03:31)

$ pnpm -C web lint && pnpm -C web typecheck && pnpm -C web test
Test Files  16 passed (16)
     Tests  222 passed (222)
```

那 11 條紅**全部是 `deploy/` 的 shell 腳本測試**（`test_entrypoint.py` 4 條、`test_qbittorrent_preseed.py`
7 條），原因是這台機器的 PowerShell 裡 `bash` 先解析到 WSL 的 `System32\bash.exe`（exit 127）。Git Bash
放到 PATH 最前面之後剩 `test_entrypoint.py` 兩條，而那兩條在乾淨的 HEAD worktree 上同樣紅——不是這一票
造成的，細節在 Comments。`pnpm gen:api` 重產後 `schema.d.ts` 雜湊不變。

**M1 驗收實跑**（2026-09-15，brief §17 M1 那一列）：`deploy/docker-compose.yml` 加一份覆寫——berth 用這個
工作目錄 build 的 image、`/data` 是 Docker Desktop VM 的 ext4 named volume（發佈名太長，Windows bind mount
的 260 字元路徑放不下）、多一台只送 `.torrent` 的 http.server。服務全是真的：qBittorrent 5.2.3、
Jellyfin **12.0.0**（`lscr.io/linuxserver/jellyfin:latest`）、Prowlarr、真的 TMDB。精靈八步全走 API。
三包的檔案清單取自 benchmark 語料（`tests/fixtures/parser/`），影片是 330 秒的真 MKV / MP4，`.torrent` 由
那些位元組算出來；Berth 自己抓 torrent、自己送單。**下載的替身**：問 qBittorrent 它的下載路徑、把檔案放
過去、`recheck`——沒有 peer，這一步取代的只是「位元組到了」。

- 07:06:28 → 07:06:38：The Bear S03（10 集）、Frieren S01（28 集 + 11 集 Specials）、Oppenheimer 三筆
  **不經人工**走到 `imported`，時間線是 `created → submitted → metadata_received → (preplan) → completed →
  plan_generated → linked ×N → jellyfin_scan_requested`。
- 硬鏈接（容器內 `stat -c '%i %h %n'`）：`88164 2 …/complete/tv/The.Bear…S03E01….mkv` 與
  `88164 2 /data/library/tv/The Bear (2022) [tmdbid-136315]/Season 03/The Bear (2022) - S03E01 - Tomorrow
  [WEB][1080p][SuccessfulCrab].mkv`；帳本 50 筆正片 `source_inode == target_inode` 全部成立。
- Jellyfin（API 與 playwright 截圖）：大熊餐廳 (2022) `Tmdb=136315` S3 10 集（S3E1 翌日 … S3E10 永遠）、
  葬送的芙莉蓮 (2023) `Tmdb=209867` Specials 11 集 + 第 1 季 28 集、奧本海默 (2023) `Tmdb=872585`，
  三部的 `/Items/{id}/Images/Primary` 都是 200 `image/jpeg`，詳情頁的海報、季卡片與集縮圖都畫出來了。
- 07:29:21：Berth 反查到全部 50 個 item（`jellyfin_item_resolved` 10 / 39 / 1）並觸發 MergeVersions
  （劇集任務 ×2、電影任務 ×1，Jellyfin 回 204）。
- **實跑抓到的缺陷**：入庫之後 Jellyfin 一個 item 都沒出現——路徑通知對從沒掃到過內容的媒體庫無效（brief
  §20.1）。修成 resolver 第二次沒找到就跑 `RefreshLibrary`；換 image 重起 berth 之後，07:19:21 由 Berth
  自己觸發掃描，十分鐘後那一次反查全部找到。診斷時手動打過一次 `POST /Items/{id}/Refresh`（沒有效果），
  沒有手動改帳本、沒有手動觸發掃描。
- 下載列表的展開區（playwright）：計劃「已套用 · 10 個檔案要入庫 · 信心 high 10」、10 行「已鏈接」各帶目標
  路徑、「已通知 Jellyfin · 通知了 10 個檔案的路徑」，沒有任何原樣的型別字串或 i18n key。

## Comments

這一票**沒有做**、或做法與票上字面不同的地方（每一條都記在 `docs/progress.md` 的「偏差與決定」）：

- **「不可跳過」定義為正片**：字幕與特典鏈接不成只記在那一列上、不擋 `imported`。
- **目標上有別人的檔案時走 `importing` → `review`**（plan §3.1 的表原本沒有這一條），其餘不衝突的
  檔案照樣鏈接。M1 沒有審核佇列，所以下一步是「把那個檔案移走、按重新規劃」——計劃那一塊說得出來。
- **`jellyfin_resolver` 不是事件驅動**：每 15 秒醒一次，排程存在帳本上（`resolve_after`）。
- **MergeVersions 在反查成功之後觸發**，不是入庫當下；用精靈存下的任務 Id。
- **反查也比 `MediaSources[].Path`**：`/Items` 因此帶整份 MediaSources（含串流資訊），媒體庫大的時候
  那一支很重。M2 的對帳會把整個媒體庫走一遍，那時候再決定要不要分兩段取（先 `Path`、對不上的
  才要 MediaSources）。
- **事件去重是查最近一分鐘的同型別事件**，沒有 payload hash 欄位；使用者按下的重試是界線。
- **resolver 每一輪把還沒找到的路徑再通知一次**：入庫當下那一次通知可能沒送到。
- **沒找到兩次以上就跑 Jellyfin 的「重新掃描媒體庫」排程任務，之後最晚 10 分鐘再看**（票面寫的是
  「30s → 2m → 10m → 1h 共 6 次」）。實跑抓到：路徑通知對從沒掃到過內容的媒體庫無效（Jellyfin 12.0.0，
  brief §20.1），而套件內的媒體庫一開始一定是空的。代價是媒體庫大的時候那一次掃描要走完整棵樹。
- **MergeVersions 合併之後，帳本上的 `jellyfin_item_id` 可能不再是主條目**（第二個版本在合併前是
  一個重複的 Episode，反查存下的是它的 id）。這一輪的驗收沒有多版本資料，驗不到；M2 的對帳重新
  反查時處理。
- **`jellyfin_item_resolved` 一筆 Job 一行、只帶 `count`**，不是 brief §5.2 的 `(item_id)`。
- **`tests/unit/test_entrypoint.py` 與 `test_qbittorrent_preseed.py` 在這台機器上紅**，與這一票無關：
  PowerShell 裡的 `bash` 先解析到 WSL 的 `System32\bash.exe`（不認 `C:/…` 腳本路徑，exit 127）；
  Git Bash 放到 PATH 最前面之後剩 `test_entrypoint.py` 兩條，而乾淨的 HEAD worktree 上同樣是這兩條紅。
  留給票 15 的收尾。
