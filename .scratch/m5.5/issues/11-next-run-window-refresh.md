# 11 — 換輪、提醒視窗與巡檢前刷新

**Status:** ready-for-agent

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

- [ ] Re:Zero fixture（E77 之後停播 56 天）開的是 `next_run`；同一輪停播 14 天仍是 `late`（測試）
- [ ] 播出超過 60 天的不開（測試）
- [ ] 覆寫門檻生效，多條訂閱取最大值（測試）；RSS Series 表單改得到（playwright 實跑）
- [ ] 刷新失敗的作品，開著的 Issue 不被收掉、也不開新的（測試）
- [ ] 一輪巡檢的 TMDB 請求數有上界（fake client 計數）
- [ ] 全部檢查、pytest、vitest 綠；progress.md 已更新
