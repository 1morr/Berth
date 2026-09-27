# 12 — 作品頁的「下載」段：這部作品的 torrent 與檔案

**Status:** done

**Blocked by:** 04（下載列表的分頁與 query key 先定，這一段重用它）

**讀:** brief §12、§13；plan §6（jobs 群組）、§7；`.scratch/m1/media-detail-shape.md`、`.scratch/m1.5/media-detail-shape.md`；開工先 `/impeccable shape` 這一段

## 為什麼（2026-09-26 使用者試跑）

作品頁的季表只在集數上標「下載中」，看不到是哪些 torrent；還沒入庫時「檔案與版本」寫「還沒有任何檔案入庫」，
整頁像什麼都沒發生——KAIJU GIRL CARAMELISE 的 12 個 torrent 在 qBittorrent 排隊中，作品頁一個都看不到。
使用者要在作品頁看到相關的 torrent，展開看裡面的檔案，下載中、未入庫的也要。

## 做什麼

1. 作品頁新增「下載」段：這部作品的 Job（`jobs.media_id`）——名稱、狀態、進度、大小、來源（手動 / RSS 與哪個 Series）、
   Route、時間；每一列展開看 `job_files`（檔名、大小、Plan 對到的季集），連到 Job 詳情。預設只列還沒入庫與需要人的，
   已入庫的收在「顯示全部」後面。
2. 季表的「下載中 / 待確認」標籤連到那一個 Job。
3. SSE 的即時更新沿用 04 的合併失效（這一段的 query key 在 `['jobs']` 前綴下或另立，照 04 定的規則）。
4. `GET /jobs?media=` 或同等的篩選，`pnpm gen:api` 同一個 commit。

## 驗收

- [x] 有排隊中、下載中、已入庫、待確認四種 Job 的作品：「下載」段列出前兩種與待確認，展開看得到檔案（vitest + playwright，1280 與 390）
      —— shape 時使用者拍板「待確認」＝已入庫而 audit 還掛著的，預設那一組叫 `open`（還沒了結）。vitest：`MediaDetailPage.test.tsx`
      的「下載段」九條（四種都列、確認過的只在「全部」、展開看檔名 / 大小 / 季集 / 不下載、沒檔案清單、全部了結、從沒送過不畫、
      翻過最後一頁）；後端 `test_jobs.py::TestAWorksDownloads` / `TestAJobsFiles`、`test_jobs_api.py`。playwright：新演練情境
      `downloads`（`_seed_downloads` 五筆）與前端 e2e `media-downloads`（1280）/ `media-downloads-390`，兩條都綠；390 頁面層級
      橫向捲動 0。截圖 `.playwright-mcp/t12-1280.png`、`t12-390.png`（不進版控）。
- [x] 季表的標籤點得到那一個 Job（vitest）
      —— 「下載中」與「卡住」都連到 `/jobs/:hash`（`EpisodeOut.job`，兩筆蓋到時最新送的那一筆；後端 `test_media_holdings.py`）。
      vitest 兩條（下載中、卡住），e2e 也點得到。
- [x] 下載進度即時更新（playwright 對演練情境）
      —— 替身 `TricklingQbittorrent` 每一輪 +7%（5%–95% 循環），spec 取兩次樣、斷言會變；這一段的 key 在 `['jobs', 'list', …]`
      與 `['jobs', hash, 'files']`，票 04 的合併失效直接涵蓋。
- [x] brief §13 同步 —— Media 詳情那一列；plan §6 的 jobs、media、events 三列也改了。
- [x] lint、type、test、前端 e2e 綠燈 —— 指令輸出見 progress.md 同日那一行。前端 e2e 33 條過 32，紅的 `rss-preview-390`
      單獨重跑綠（見 Comments）。

## Comments

- **前端 e2e 的 RSS 時序 flake 又一條**：整套一起跑時 `rss-preview-390` 的「立即輪詢」回「新 0 筆」，單獨重跑綠；上一輪整套跑則是
  `rss-subscribe` 兩條紅、這一輪綠。與票 04 Comments 記的同一類（輪詢與預覽在負載下被規劃器餓住），不是這張票碰的東西。
- **季表跟隨是啟發式**（`DownloadsPanel.useSeasonsFollow`）：看得到的列換了狀態或算出計劃、或件數變了，就讓 `['media', id]` 重問。
  不在這一頁、件數也沒變的那幾筆換了狀態看不到；換篩選時先拿到快取裡較舊的那一頁，會多問一次季表。根本的解法是讓 SSE 失效
  作品的季表（2026-09-26 審查記過、沒開票），不在這一張。
- code-review 留著沒改的（判斷題）：
  - `JobOut.series` 讀不出字幕組時退回 Series 的原始標題；`/rss/series` 與審核佇列的 `group` 沒有這個退回，同一個詞在 API 上兩種值。
  - `DownloadRow` 與 `JobRow` 的 `<details>` 外殼、`DownloadsPager` 與 `JobsPager` 的 `announce` 形狀相同；只抽了摘要（`JobSummary`）
    與外框（`jobRowFrame`，放在 `jobState.ts`）。
  - `EpisodeState` 留著「卡住 / 下載中但沒有 `job`」的分支：後端兩種都給，只是型別是 nullable。
