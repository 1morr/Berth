# Berth

自託管的媒體取得與入庫協調器：把索引站或 RSS 命中的 torrent 送到 qBittorrent，下載完成後解析、比對 TMDB、以硬鏈接入庫到 Jellyfin，並維護可修復的帳本。本檔只是名詞表；決定與事實在 `docs/design-brief.md`，實作在 `docs/plan.md`。

## Language

### 媒體與目的地

**Media**:
TMDB 上的一部電影或一部劇集，鍵為 `movie:<tmdb id>` / `tv:<tmdb id>`；劇集底下有 Season 與 Episode，編號沿用 TMDB。
_Avoid_: title, show, series, item

**Tracked Media**:
Berth 曾為其下載、訂閱或入庫過的 Media。
_Avoid_: subscribed media, library item

**Library Route**（UI 顯示「媒體庫」）:
一個入庫目的地：Jellyfin 媒體庫、一個寫入目標路徑、一個 qBittorrent category、一個命名 profile（standard / anime）。
_Avoid_: root folder, destination, library（程式碼中）

**Profile**:
Route 的命名與解析偏好，`standard` 或 `anime`。
_Avoid_: series type, mode

**Complete / Incomplete root**:
qBittorrent 的完成與未完成下載根目錄；complete 是硬鏈接的來源。
_Avoid_: download folder, save path（僅指 qBittorrent 的欄位時可用）

### 取得

**Download Job**（簡稱 Job）:
一個 torrent 在 Berth 中的生命週期紀錄，以 info hash 為鍵。
_Avoid_: torrent（指 Job 時）, download, task

**Trigger**:
Job 的來源：`manual`、`rss:<rule>`、`reimport`。
_Avoid_: source, origin

**Search Result**:
索引站回傳的一筆候選 torrent，附解析出的 Tags 與預估季集。
_Avoid_: release（僅指發佈名解析時可用）

### 入庫

**Import Source**:
待入庫的檔案集合：Job 的內容目錄，或 complete 下的任一目錄（重新入庫時）。
_Avoid_: input, folder

**Release Info**:
從發佈名或檔名解析出的結構化欄位（標題候選、季、集、版本、字幕組、來源、解析度、字幕語言…）。
_Avoid_: parse result, metadata

**Tags**:
一個檔案版本的可辨識屬性集合（source、resolution、subs、hardsub、group、version、edition），以固定 token 渲染進檔名。
_Avoid_: quality, flags, labels

**Candidate**:
對一個影片檔的一種季集對應，附策略、信心與理由。
_Avoid_: match, guess

**Import Plan**（簡稱 Plan）:
對一個 Import Source 逐檔決定分類、對應 Media / 季 / 集、目標路徑、Tags、信心與理由的可審核計劃；套用前不動任何檔案。
_Avoid_: mapping, import job, rename plan

**Plan Item**:
Plan 中一個檔案的決定，`action` 為 import / extra / subtitle / skip / unmatched / review。
_Avoid_: entry, row

**Confidence**:
Plan Item 的三級信心：high、medium、low。high 與 medium 自動入庫，low 進 Review Queue。
_Avoid_: score, probability

**Audit**:
medium 信心自動入庫後掛的旗標，在 Review Queue 顯示為「已入庫待確認」。
_Avoid_: pending, provisional

**Ledger Entry**:
一條「來源檔案 → 目標硬鏈接」的紀錄，含 hash、來源相對路徑、目標路徑、inode、Media / 季 / 集、Tags、plan item、Jellyfin item id。
_Avoid_: link record, file record, history

**Extras**:
可辨識但不屬於正片的內容（NCOP / NCED、PV、CM、Menu、預告、花絮、特典映像），入庫到 Jellyfin 的 `extras/`。
_Avoid_: bonus, specials（Specials 指 TMDB season 0）

**Unmatched**:
解析後對不到 TMDB 任何一集或一部的影片或字幕檔；留在 complete，不入庫。
_Avoid_: unknown, orphan（Orphan 是對帳用語）

**Review Queue**:
需要人工處理的統一清單：低信心 Plan、Audit、Unmatched、重複版本、Issue。
_Avoid_: inbox, pending list, interactive import

**Rematch**:
把已入庫或 Unmatched 的檔案改指派到另一季集、標為 Extra 或忽略；一律經過 Plan。
_Avoid_: fix, remap, move

**Reimport**:
以 complete 下的目錄為 Import Source 重新入庫。
_Avoid_: re-run, resync

### 修復

**Reconciler**:
比對帳本、qBittorrent、complete 目錄、library 目錄四方一致性的排程工作。
_Avoid_: scanner, sync, health check（Health Check 指服務與 Route 連線）

**Issue**:
Reconciler 或管線發現的不一致，有固定型別（library_link_missing、source_missing、inode_mismatch、orphan_complete、unknown_torrent、unmanaged_library_file、job_without_files）。
_Avoid_: error, problem, orphan（僅作 Issue 型別名的一部分）

**Unmanaged**:
library 內不是 Berth 建立的檔案；只列出，永不刪除。
_Avoid_: foreign, external, legacy

**Delete Scope**:
刪除時可組合的四個旗標：移除 library 鏈接、從 qBittorrent 移除 torrent、刪除 complete 檔案、清除帳本。
_Avoid_: purge level, cleanup mode

**Health Check**:
對服務連線、版本、Route 硬鏈接與跨服務可見性的檢查，結果顯示在健康頁。
_Avoid_: diagnostics, status check

**Event**:
Job 時間線上的一筆事件：型別、時間、actor、payload。
_Avoid_: log, activity, history

### RSS

**Feed**:
一個 RSS 來源（Mikan、Nyaa、generic），有輪詢間隔。
_Avoid_: subscription（Subscription 是 UI 上「訂閱一部作品」的動作）, source

**Rule**:
綁定 Media 與 Route 的自動下載規則：包含 / 排除條件、字幕組、解析度、字幕偏好、季與集 offset、策略。
_Avoid_: filter, subscription rule, watch

**Feed Item**:
Feed 中的一筆項目及其解析與比對結果（new / matched / downloaded / ignored / unmatched）。
_Avoid_: entry, post
