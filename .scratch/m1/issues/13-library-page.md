# 13 — 媒體庫頁、版本清單與 Jellyfin 深連結

**Status:** done

**Blocked by:** 12

**讀:** plan §7、§11.2（T1.7）；brief §12、§13（媒體庫、Media 詳情）

## 做什麼

入庫的東西要看得見、點得進去播。媒體庫頁依 Route 分頁、卡片牆顯示已入庫作品與狀態，點卡片
深連結到 Jellyfin 播放；Media 詳情頁補上最後一塊——檔案清單與多版本並存清單。

深連結用 ledger 的 `jellyfin_item_id`；反查還沒完成或耗盡時要說明原因，不給死連結。

Berth 不做內嵌播放器（brief §12），播放一律交給 Jellyfin。

## 驗收

- [x] `/library/:routeSlug` 依 Route 分頁，卡片牆顯示已入庫作品與狀態（使用者拍板：牆上是這條 Route
      上有 Job 的全部作品，含還沒入庫的）
- [x] 篩選：有 Unmatched / 有待審（資料來源是 plan 與 ledger；Issue 篩選留 M2）
- [x] 卡片深連結到 Jellyfin 的該作品；`jellyfin_item_id` 還沒反查到時說明原因而不是死連結（劇集連
      Series，靠新的 `jellyfin_series_id`；卡片本體連 Media 詳情，深連結是並排的另一條，使用者拍板）
- [x] Media 詳情頁補上檔案清單：每個檔案的季集、Tags、目標路徑、ledger 狀態（外加 Jellyfin 反查狀態與
      對不到的檔案）
- [x] Media 詳情頁補上多版本並存清單（brief §7.7；劇集經 MergeVersions 合併後顯示的是整個檔名主幹）
- [x] Media 詳情的各集狀態反映實際入庫情形（使用者拍板五種：已入庫 / 卡住 / 下載中 / 缺 / 未播出）
- [x] 一條 Route 都還沒有東西時的空狀態說得出下一步該做什麼
- [x] 媒體庫頁走 `/impeccable shape`（`.scratch/m1/library-shape.md`）；playwright 實跑並附結果
- [x] 對比 ≥ 4.5:1；390px 窄版可用；zh-Hant 與 en 並列
- [x] lint / type / test 全綠並貼指令輸出

## 驗證

```
$ uv run ruff format berth tests scripts && uv run ruff check berth tests scripts
199 files left unchanged
All checks passed!

$ uv run mypy
Success: no issues found in 195 source files

$ uv run lint-imports
Contracts: 6 kept, 0 broken.

$ uv run pytest -q
1266 passed in 237.30s (0:03:57)

$ pnpm -C web format:check && pnpm -C web typecheck && pnpm -C web lint && pnpm -C web test
All matched files use Prettier code style!
 Test Files  18 passed (18)
      Tests  257 passed (257)
```

（在 Git Bash 裡跑：票 12 在 PowerShell 裡紅的 11 條 `deploy/` shell 腳本測試這次全綠。）

**playwright 實跑（真環境）**：票 12 的驗收那一套（Jellyfin 12.0.0、qBittorrent 5.2.3、真的 TMDB），berth
換上本票工作目錄 build 的 image（換之前先備份資料庫）。

- `/library` 落在第一條 Route `/library/movies`：`MOVIE · 2023 | 已入庫 | 奧本海默 | Oppenheimer | 1 個版本 |
  在 Jellyfin 開啟`，href `http://localhost:8096/web/#/details?id=662076cd30fb5b73989bcd7fb95753db`（套件內的
  Jellyfin：瀏覽器主機名 + 8096）。**開那一條連結，真的 Jellyfin 畫出「奧本海默」**，版本選單是
  `Oppenheimer (2023) [tmdbid-872585] - [BD][1080p][YTS.MX]`。
- `/library/tv`：`部分 | 大熊餐廳 | 10 / 46 集入庫 | Jellyfin 還在掃描`——這一季是本票之前反查的，帳本沒有
  Series id，所以不給一條連到某一集的連結（見 Comments）。
- 不帶 `serverId` 的深連結：登入後開 `/web/#/details?id=b26853ef1000814d9563768d24869a99`（Series），真的
  Jellyfin 畫出「大熊餐廳」與「第 3 季」。
- `/media/tv:136315`：季列 `S03 · 10 / 10 集入庫`、`S01 · 0 / 8 集入庫`；S03 各集「已入庫」、S01 各集「缺」；
  「檔案與版本」10 列，逐列 `正片 · S03E01 · [WEB][1080p][SuccessfulCrab]`、完整目標路徑、`帳本 對得上 ·
  Jellyfin 已收錄`。
- 對比與窄版：`/library/movies`、`/library/tv`、`/media/tv:136315`、`/settings/services` × 深淺兩主題 × 1280 /
  390px，逐一計算每個有文字的元素對它實際底色的對比——**深色最低 6.53:1、亮色最低 5.71:1**，390px 頁面
  層級橫向捲動 0。截圖在 `.playwright-mcp/ticket13/`（gitignored）。

**playwright 實跑（`inventory` 演練情境）**：真的 TMDB，替身 Jellyfin 會「掃到」入庫的檔案，送單、poller、planner、
importer 與 resolver 全是產品自己的程式碼。兩包送進 Anime 之後：

- `/library/anime` 那一格：`TV · 2022 | 待審 | SPY×FAMILY 間諜家家酒 | SPY x FAMILY | 3 / 50 集入庫 | 在 Jellyfin 開啟`。
  深連結的 id 是 resolver 走完兩段查詢、從 Episode 的 `SeriesId` 寫進帳本的那一個。切換列
  `Movies 0 部 | TV 0 部 | Anime 1 部`，篩選 `全部 | 待審 1 | Unmatched 0`。
- 按「待審」：剩 1 格、網址是 `?filter=review`、`aria-live` 說「顯示 1 部作品」。按「Unmatched」：0 格，
  說「沒有 Unmatched 的作品。」與「顯示全部」。
- `/media/tv:120089`：`S01 · 3 / 25 集入庫`、E01–E03「已入庫」、E04 起「缺」；「檔案與版本」5 個檔案（外掛字幕、
  三集正片、NCOP 特典），正片「Jellyfin 已收錄」，版本那一塊說「每一集都只有一個版本。」。
- 同樣三個畫面（含 `?filter=review`）× 深淺 × 1280 / 390px：深色最低 6.53:1、亮色最低 5.71:1，橫向捲動 0。

## Comments

這一票**沒有做**、或做法與票上字面不同的地方（每一條都記在 `docs/progress.md` 的「偏差與決定」）：

- **程式碼叫 inventory**：`CONTEXT.md` 的 `library` 指 Jellyfin Library，網址仍是 `/library/:routeSlug`。
- **深連結不帶 `serverId`**，只在 12.0.0 驗過；10.10 / 10.11 沒測不帶的形式。
- **本票之前就反查完的劇集沒有 `jellyfin_series_id`**，卡片會一直說「Jellyfin 還在掃描」，直到 M2 的對帳
  重新反查。沒有做回填：migration 裡問不了 Jellyfin，而在 resolver 裡為舊資料加一條補填路徑是相容層。
- **真環境裡沒有待審、Unmatched 或失敗的作品**，那幾種卡片與兩個篩選由前端測試與 `inventory` 演練情境驗。
- **沒有 Issue 篩選**（票面寫明留 M2）。
- **TDD 的偏差**：`services/inventory.py` 的牆那一組測試是整批寫完再寫實作，不是一條一條紅轉綠；其餘接縫
  （resolver、各集狀態與檔案、API、前端三頁、深連結純函式）都先看過紅燈。

code-review（兩軸，基準 `6baef14`）**處理了的**：前端 `Library*` 改名 inventory、卡片的 `·` 改用 `Dot`、
導覽方塊類名共用、`owning_route` 拿掉多餘的泛型、`aria-label` 不再掛在 `<p>` 上、holdings 從
`services/media.py` 搬到 `services/inventory.py`、沒有多版本時說一句話、只有 Unmatched 時也說「還沒入庫」、
季列的計數改由後端算、多版本以資料夾分組。

code-review **沒處理、留著的**：

- 「Jellyfin 找到了沒」後端兩支（`presence_of` 看作品、`_file_presence` 看單一檔案）：語意不同——牆上那一格
  要 Series id，一個檔案不必——所以不合併。
- 失敗 / 卡住 / 在路上的狀態分類，後端 `inventory.py` 與前端 `jobState.ts` 各一份：跨語言，共用不了。
- `season` / `episode_start` / `episode_end` 三欄一起旅行（Data Clumps）：它們是 plan §2.3 的欄位形狀，
  `Covers` Protocol 已經收住讀取端。
- 空狀態容器的類名在 `InventoryPage` 裡重複三次：與 `JobsPage` 同一個寫法，抽出來不比較清楚。
- **探索牆既有的兩處同類問題沒改**（票 03 留下的）：`MediaTile` 的 `·` 沒有 `aria-hidden`、`MediaWall` 的筆數
  `aria-label` 掛在 `<p>` 上。留給票 15 的 `/impeccable audit`。
- impeccable hook 回報 `.impeccable/design.json` 比 `DESIGN.md` 舊（沒有照 skill 規則自動修），留給票 15 的
  `/impeccable document`。
