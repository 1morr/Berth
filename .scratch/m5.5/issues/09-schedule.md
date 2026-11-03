# 09 — 時間表最小版

**Status:** ready-for-agent

**Blocked by:** 07, 08

**讀:** spec〈範圍〉「新番區塊」「時間表」；brief §20.3（含 08 的結論）、§13；plan §7；`docs/research/` 裡 08 留下的數字；`.scratch/m5.5/navigation-shape.md`

## 為什麼

找得到當季新番，並一鍵走到訂閱。時刻與評分（14）、「晚 N 天」（12）是之後的層，這張先端到端跑通。

## 做什麼

1. **先 `/impeccable shape`**：版面照 AutoBangumi Calendar（brief §20.3）。輸出 `.scratch/m5.5/schedule-shape.md`。
2. **資料**：TMDB 當主幹（08 量過，brief §20.3、`docs/research/schedule-sources-2026-11-04.md`）列本週當季新番。
   - `discover/tv`：`with_genres=16`、`with_original_language=ja|zh`，`air_date.gte` 為週一前一天、`air_date.lte` 為週日後一天（深夜檔兩邊差一天），全部頁數。
   - discover 的每筆沒有集與播出日：每部再讀 `tv/{id}` 的 `last_episode_to_air` / `next_episode_to_air`，照 TMDB 的 `air_date` 放進那一天的欄。
   - 約一半是長壽 / 兒童節目與國產動畫（Bangumi 放送表沒有的）；要不要篩看版面再定，篩的話記在票的 Comments。
   - 有人打開才抓，結果存程序內 `TtlCache`（6–24 小時），不為卡片寫 `media` 列。
   - 卡片的狀態每次照資料庫算，不進快取，所以訂閱完下一次打開就變。
   - 讀取命令 `Effect.READ`，每個人都能讀；端點進路由表。
3. **頁面**（`/schedule`）：
   - 週一到週日分欄、今天標出；手機是單日清單。
   - 預設列全部（AutoBangumi 只列已訂閱，這裡要拿來找新番），可切「只看已訂閱」。
   - 卡片：海報、顯示用標題（Display Round）、第幾集、狀態（未訂閱 / 已訂閱 / 已入庫）。點進 `/media/:id` 走現有的訂閱流程。
   - 一般使用者看得到狀態類別，看不到字幕組與 Feed（比照 `services/why_not.py` 的範圍）。
4. **導覽**：「新番」對所有人顯示，分頁為時間表 `/schedule`（預設，每個人）、訂閱 `/rss`（admin）。
5. Fake 後端補時間表的資料，UI 驗證不需要金鑰；`docs/development.md` 的情境表補一列（如有新情境）。
6. 文件：brief §13、plan §7 路由表、`CONTEXT.md`（時間表的名詞，若有新詞）。

## 驗收

- [ ] 時間表列出本週當季新番；未訂閱的卡片點進作品頁訂閱成功，下一次打開變「已訂閱」（e2e，桌機與 390px）
- [ ] 一般使用者看得到時間表與狀態，看不到字幕組與 Feed；看不到「訂閱」分頁（測試＋e2e）
- [ ] 同一個快取期間內再打開不再打外部來源（fake client 計數）
- [ ] 全部檢查、pytest、vitest、前端 e2e 綠；progress.md 已更新
