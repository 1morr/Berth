# 11 — 換輪、提醒視窗與巡檢前刷新

**Status:** done

**Blocked by:** 10

**讀:** spec〈範圍〉「遲到判定」的換輪、視窗、門檻覆寫，與「巡檢前刷新」；brief §20.12；plan §2.4；`services/media.py`（`PLANNING_TTL`、`_load`、`_store`）；`services/sweep.py`（`sweep_once`、`_settle`）

## 為什麼

10 只會說「晚了」。字幕組沒遲到、只是下一個 cour 沒訂（Mikan 上是另一個番組，brief §20.12）時不該誤報；斷更很久的不該每天提醒；TMDB 快照舊了就看不到剛播出的集。

## 做什麼

1. **換輪**：基準那一集與下一集播出日相隔超過 21 天，`reason = next_run`，不是字幕組遲到。作品上有一條比基準那一集入庫更晚建立的 RSS Series 時回到一般判定。
2. **視窗**：最後一集缺集播出滿 60 天後不再提醒（追更頁會放在「斷更很久」，見 12）；上線第一天的舊缺集也走這一條。
3. **單一 RSS Series 覆寫門檻**：`rss_series.overdue_days`（新增可為空的欄位，留空用全域設定）；一部作品多條訂閱取最大值。RSS Series 的編輯表單多一格。
4. **巡檢前刷新**：在巡檢的交易之前、用獨立 session 刷新有綁定作品的快照（`_store` 自己會 commit，所以不能放進 `sweep_once`）。
   - 跳過 6 小時內刷新過的（`PLANNING_TTL`），以及 TMDB 說完結且都在庫的。量級：一部 5–7 次請求，20 部約 100–150 次，全域桶每秒 40 次。
   - **刷新失敗的作品這一輪不開也不收**：`_load` 把錯誤吞成回傳值，要看 `tmdb_fetched_at`；`_settle` 收掉「沒被標出」的件時要排除這些作品。
5. 文件：plan §2.4、`CONTEXT.md`（換輪）。

## 驗收

- [x] Re:Zero fixture（E77 之後停播 56 天）開的是 `next_run`；同一輪停播 14 天仍是 `late`（測試）
- [x] 播出超過 60 天的不開（測試）
- [x] 覆寫門檻生效，多條訂閱取最大值（測試）；RSS Series 表單改得到（playwright 實跑）
- [x] 刷新失敗的作品，開著的 Issue 不被收掉、也不開新的（測試）
- [x] 一輪巡檢的 TMDB 請求數有上界（fake client 計數）
- [x] 全部檢查、pytest、vitest 綠；progress.md 已更新

## Comments

- 2026-11-04 **協調者追加**（票 10 的缺陷）：`_overdue_works` 的對象原本是所有綁好的 RSS Series，而 `delete_feed` 只刪 Feed、Series 與綁定留著，退訂後每日巡檢仍會開 `episodes_overdue`。改成作品在 `rss.subscribed_media`（與作品頁的訂閱清單同一套）裡，而且那一條 Series 還帶著 Item（Feed 刪了連 Item 一起刪）；作品還訂著時，Feed 被刪的那幾條也不參與門檻、換輪與起算日。先寫紅燈（`TestUnsubscribed`：刪 Feed 後不開、已開的收掉），merge main（0b3bc78a，fast-forward）拿到 `subscribed_media`。
- 換輪：基準那一集與下一集相隔 `> 21` 天（21 天算同一輪）；比基準那一集**入庫時刻**更晚建立的 Series 回到 `late`；還沒入庫過沒有基準，一律 `late`。跨季（S1 末 → S2E1）隔很久也算換輪。
- 視窗是整部作品：最後一集缺集（基準之後已播、沒入庫的最新一集，過不過門檻都算）播出滿 60 天就整部不提醒；還在提醒時，之前晚的集照實列出。
- 判定的簽名改成 `imported: Mapping[(季, 集), 入庫時刻]`、`subscribed: Collection[建立時刻]`（原 `watched_since` 改由最早那條算）。
- 巡檢前刷新：`media.refresh_snapshot`（`_load` 抽出不組視圖的 `_pull`；`snapshot_for_planning` 也改走它）、`sweep.refresh_watched`，`Sweeper` 多收 `clients`。失敗看 `_pull` 的回傳型別（與看 `tmdb_fetched_at` 等價）；非服務錯誤逐部接住、rollback、記成那一部失敗。**沒設 TMDB key 時每一部都算刷新失敗**，已開的遲到不會被收掉，直到有 key（照「不開也不收」的字面）。
- Issue 頁 `reason = next_run` 時多一行「可能是下一輪」（票 12 的追更頁另做）。
- `rss-sweep` 替身情境：SPY×FAMILY 是 2022 年播的，過了 60 天視窗，不再開遲到；Series 掛到 Mikan 聚合 feed 的一筆「略過」Item 上（還訂著）。票 12、13 若要遲到的替身，要另做有近期播出日的作品。
- 前端 e2e（協調者要求，合併前）：重新 build 後 `pnpm -C web exec playwright test` 85 passed（2.7 分），8484–8534 跑前沒人佔。
- playwright：`rss-sweep` 實跑 `/rss`，展開 SPY×FAMILY 的字幕組，「進階」裡存 5 讀回 `overdue_days: 5`、清空存讀回 `null`、填 31 欄位下說「填 0 到 30 的整數，或留空」不送出；390px 版面正常。
- code-review 已處理：`snapshot_for_planning` 改呼叫 `refresh_snapshot`、刷新失敗的排除抽成具名變數、前端共用 `OVERDUE_DAYS_MAX`、刪 Feed 的 Series 逐條排除、刷新例外逐部隔離、視窗錨點改成最後一集缺集、補 `sweep_once` 的換輪整合測試。未處理（判斷題）：
  - `_watched_series` 一輪跑兩次（刷新一次、巡檢一次），`_imported` 在刷新的跳過檢查多查一次；量級小。
  - `IssueRow` 直接比 `detail.reason === 'next_run'`，沒有型別守衛；理由再多一種時再補。
  - 新 migration 只加可為空的欄位、不回填（spec〈共同規則〉已列），沒另外問。
