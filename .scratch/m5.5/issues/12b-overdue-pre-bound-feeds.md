# 12b — 預先綁定、還沒收到任何一集的訂閱也看遲到

**Status:** done

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

- [x] 預先綁定、一集都沒收到、播出過門檻 → 開 `episodes_overdue`，追更頁列在「要你動手」（整合測試，修前紅）
- [x] 刪掉那條 Feed → 不開，已開的收掉（整合測試）
- [x] 有 RSS Series 的作品行為不變（既有測試綠）
- [x] 追更頁實跑看得到這一列（playwright，桌機與 390px）
- [x] 全部檢查、pytest、vitest、前端 e2e 綠；progress.md 已更新

## Comments

- 2026-11-04 欄位：票說 `RssFeed` 沒有 `created_at`，其實有（`models/rss.py`）。`media_id` 只在 `rss.subscribe_search` 建 Feed 時寫、之後不改，所以綁定時刻就是 `created_at`：不加欄位、不加 migration，舊列本來就有值（`codebase-design`：不另存一份會跟既有欄位重複的時刻）。plan §2 的資料表不變。
- 形狀：`keeping_up.watched_works` 改回每部作品一份 `Subscriptions(series, feeds, grown)`，巡檢、追更頁、時間表三處都讀它。`starts()` 含每一條預先綁定的 Feed（長出 Series 的也算，起算取較早的）；門檻與字幕組欄只看還沒長出 Series 的 Feed（`grown` 之外），長出來之後由那條 Series 代表。
- 取捨（code-review 提出，照票的字面做，留給使用者知道）：
  - 從作品頁訂、已經長出 Series 但還沒入庫過的作品，起算從 Series 建立提早到 Feed 綁定（票第 2 點「較早的那一個」）；與驗收「有 RSS Series 的作品行為不變」有拉扯，差距是建 Feed 到第一次輪詢長出 Series 的那段時間。既有測試的 Feed 都沒有 `media_id`，不受影響。
  - `watch_overdue` 的 `subscribed` 同時決定起算與換輪，所以基準之後才綁定的 Feed 也把 `next_run` 翻回 `late`，與「更晚建立的 Series」同一條規則（測試 `test_a_feed_bound_to_the_next_run_brings_back_late`）。
  - 作品有 Series（覆寫成比全域小的門檻）又有還沒長出 Series 的 Feed 時，門檻被那條 Feed 拉回全域（spec「多條訂閱取最大值」）；沒有測試。
- 替身 `tracking` 情境加《我獨自升級》：五天前預先綁定 Sakurato 的 Nyaa feed、一集都沒收到，第 3 集三天前播。playwright 實跑（e2e `tracking` / `tracking-390`）讀回截圖：桌機與 390px 都在「要你動手」，字幕組 Sakurato、已入庫到「還沒有」、「晚 3 天」「字幕組還沒發」，沒有橫向捲動。
- 修前紅：新整合測試共 8 支（巡檢 5、追更頁 2、巡檢前刷新 1）加時間表卡片 1 支，換回修前的 `keeping_up.py` 與 `sweep.py` 都紅，修後綠。`berth bench` auto_wrong 0 → 0（`parser/overdue.py` 只改說明）。
- code-review 已處理：`Watched` 改名 `Subscriptions`（`CONTEXT.md`〈訂閱〉不用 watch 指訂閱）；門檻用 `max(..., default=fallback)`，不靠隱性前提；`groups` 註解寫實際順序；補巡檢前刷新與時間表卡片的測試；spec、plan §3.2 的換輪與門檻敘述改成「訂閱」。
- code-review 未處理（判斷題）：
  - 字幕組名 `mikan_subgroup_name or parse_release(title_raw).group` 與 `rss._subgroup_of` 同形（票 12 搬來的，原本就重複）；「作品有哪些訂閱」在 `rss._every_subscription` 與 `watched_works` 各推一份。收成一支是另一張整理票的事。
  - `watched_works`、`watch_of`、`Watch` 這些舊名仍帶 watch，這張票不改。
