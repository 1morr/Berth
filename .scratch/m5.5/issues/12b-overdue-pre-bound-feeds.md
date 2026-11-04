# 12b — 預先綁定、還沒收到任何一集的訂閱也看遲到

**Status:** ready-for-agent

**Blocked by:** 12

**讀:** 票 10、11、12 的 Comments；spec〈範圍〉「遲到判定」「追更頁」；brief §9.1；plan §2.4、§3.2；`CONTEXT.md`〈訂閱〉；`berth/services/keeping_up.py`（`watched_works`、`watch_work`）；`berth/services/rss.py`（`subscribed_media`、`delete_feed`）；`berth/models/rss.py`（`RssFeed`）；skill `mattpocock-skills:tdd`

## 為什麼

協調者插的追加票（使用者 2026-11-04 定「按你建議」）。票 12 的 Heads up 查出：遲到與追更頁的對象（`keeping_up.watched_works`）只看「綁好、還帶著 Item 的 RSS Series」。預先把 Feed 綁到作品（`RssFeed.media_id`），而字幕組一集都還沒發時，系統裡沒有那條 RSS Series，所以這部作品不在追更頁、也不開 `episodes_overdue`。「訂了卻什麼都沒來」正是最需要提醒的情況。

使用者定：這種作品也列進來，**從綁定那天起算**。

## 做什麼

1. 對象：除了現有的 RSS Series，**預先綁定作品、還在的 Feed** 也算這部作品在看（判定照 `rss.subscribed_media`，刪掉 Feed 就不算）。
2. 基準：作品還沒入庫過時，起算點取「最早的 RSS Series 的 `created_at`」與「預先綁定 Feed 的綁定時刻」較早的那一個，之後播出的第一集算起。
   - `RssFeed` 沒有 `created_at`。照 `codebase-design` 判斷用既有欄位（例如 `primed_at`）還是新增欄位加 migration（舊列怎麼補），理由記在 Comments；改了資料表就同輪改 plan §2。
3. 門檻：沒有 RSS Series 時用全域 `RssSettings.overdue_days`；換輪（`next_run`）與 60 天視窗照舊。
4. 卡在哪：沒有 Job 時照現有的「沒有下載在處理」。
5. 追更頁：這種作品也列一列，字幕組欄寫 Feed 綁定的字幕組（`RssFeed.subgroup`），沒有就寫 Feed 名；時間表卡片的「晚 N 天」也跟著有（三處共用 `watched_works` 那一份）。
6. 文件：brief §9.1、plan §2.4、`CONTEXT.md`（若「遲到」的對象定義有寫）。

## 驗收

- [ ] 預先綁定、一集都沒收到、播出過門檻 → 開 `episodes_overdue`，追更頁列在「要你動手」（整合測試，修前紅）
- [ ] 刪掉那條 Feed → 不開，已開的收掉（整合測試）
- [ ] 有 RSS Series 的作品行為不變（既有測試綠）
- [ ] 追更頁實跑看得到這一列（playwright，桌機與 390px）
- [ ] 全部檢查、pytest、vitest、前端 e2e 綠；progress.md 已更新

## Comments
