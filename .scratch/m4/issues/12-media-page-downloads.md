# 12 — 作品頁的「下載」段：這部作品的 torrent 與檔案

**Status:** ready-for-agent

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

- [ ] 有排隊中、下載中、已入庫、待確認四種 Job 的作品：「下載」段列出前兩種與待確認，展開看得到檔案（vitest + playwright，1280 與 390）
- [ ] 季表的標籤點得到那一個 Job（vitest）
- [ ] 下載進度即時更新（playwright 對演練情境）
- [ ] brief §13 同步
- [ ] lint、type、test、前端 e2e 綠燈

## Comments
