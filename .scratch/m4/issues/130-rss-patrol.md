# 130 — RSS 的巡檢：缺集、同一集多份、一直失敗的 Feed

**Status:** done

**Blocked by:** 129

**讀:** plan §11.5〈巡檢〉與〈M3 收尾帶過來的兩條〉；brief §7.7（多版本並存）、§7.8（重複版本）、§15；M3 票 12 的 Comments（`last_error` 拆欄）；`berth/models/rss.py`；`berth/services/rss.py` 寫 `last_error` 的幾處（輪詢約 :916、:928，補漏約 :1208）；`/rss` 頁 Feed 列顯示錯誤的元件

## 為什麼

播出日比對與片長驗證漏掉的、Feed 默默壞掉的，都要有人在事後抓到。「一直失敗的 Feed」要分得出是輪詢還是補漏壞了，但兩者現在擠在同一個 `last_error`（M3 票 12）。

## 做什麼

1. **拆欄**：`rss_feeds` 的錯誤拆成輪詢與補漏兩欄（migration 把舊值搬到輪詢那欄），API 與 `/rss` 的 Feed 列分開說。
2. **一直失敗的 Feed**：輪詢或補漏連續失敗超過 24 小時，開一件 Issue，說出是哪一種、最後的原因；恢復後由系統收掉。
3. **RSS Series 缺集**：已入庫的集數之間有洞，而且洞比最新一集早超過 7 天（給字幕組晚發的時間），開一件 Issue 列出缺哪幾集，動作是到作品頁搜那幾集。
4. **同一集意外多份**：定義照 brief §7.7、§7.8——版本並存是允許的，**開工前把「意外」的判準寫進 Comments 給協調者確認再實作**。
5. 都接上票 129 的迴圈；新的 Issue 會經票 127 算進「等你處理」。

## 驗收

- [x] 拆欄 migration：舊的錯誤搬到輪詢那欄；輪詢與補漏失敗分開寫、分開顯示（pytest＋vitest）
- [x] 連續失敗超過 24 小時開 Issue、恢復後收掉；未滿 24 小時不開（pytest）
- [x] 缺集：洞比最新一集早 7 天以上才開，列出集數（pytest）
- [x] 同一集多份：照協調者確認的判準，版本並存不誤報（pytest）
- [x] 全部檢查、pytest、vitest 綠；plan §11.5 那一條標做完；CHANGELOG（含 migration 說明）、progress.md 已更新

## Comments

- **第 4 點「同一集意外多份」的判準（2026-10-22 協調者確認，照這個做）**：
  - **算**：同一個 RSS Series 底下，兩個以上**不同的 Job** 入庫成**同一集**（帳本 `import`、狀態 `ok`、同作品同季同
    起始集），而且這幾個 Job 的**發佈名寫的集號不同**（`parser.release.parse_release(job.name)` 讀出的集號；讀不出
    集號的那一筆不參與比較）。這就是「兩個不同的發佈被對到同一集」——offset、絕對編號換算、季名讀錯，播出日比對與
    片長驗證沒擋下的那一種。
  - **不算（版本並存，brief §7.7、§7.8）**：不同 RSS Series 的同一集（不同字幕組、同組在不同來源）；同一個 Series
    而發佈名寫的是同一集（同組的 v2、简／繁兩版、不同解析度、審核選「保留兩者」的 `[2]`）；同一個 Job 裡的多份；
    不是 RSS 送的（手動、`rebuild-ledger` 長回的）；帳本不在 `ok` 的（對帳那幾種 Issue 管著）。
  - **為什麼不比 Tags**：Tags 完全相同的第二份在規劃時就被 §7.8 的 `duplicate` 擋下、不會入庫（它會在第 3 點的缺集
    裡現形）；能並存進帳本的一定 Tags 不同，所以 Tags 分不出「版本」與「對錯集」，發佈名寫的集號分得出。
  - **形狀**：一個 RSS Series 一件（`IssueSubject.RSS_SERIES`，同 `first_batch_stuck`），列出每一集與撞在一起的
    發佈名；沒有動作按鈕，連到作品頁，列上寫下一步（Job 頁改正錯的那一份）；條件持續期間忽略有效（`STAYS_IGNORED`），
    條件不在了由系統收掉。
  - **code-review 補的一條**：合集看範圍。同組季末的 `[01-12]` 與每週的 `- 05` 都入庫時，照「集號」每一集都會被報；
    改成發佈名寫的集數範圍有兩個不相交才算（`sweep._apart`）——蓋到那一集的合集是「寫的是同一集」，兩段不相交的
    合集（`[01-12]` 與 `[13-24]` 對到同一集）照報。仍在上面確認過的判準之內。
- **缺集的 7 天**：從「洞之後這個 Series 最早入庫的一集」的入庫時間算，不照字面的「比最新一集早」：一集該什麼時候到
  推不出來，停更或完結之後「更新的一集」永遠不會來。缺不缺看作品頁的 `missing`（別組、手動補上的不缺，下載中與等
  審核的也不算）。progress.md 偏差有一行。
- **一直失敗的 Feed**：輪詢與補漏是兩種型別（忽略「站掛了」不該連帶忽略之後才壞的補漏）。「略過幾筆認不出 Series 的
  Item」照寫在 `poll_error`，但不起算一直失敗（code-review：Feed 讀得到，「輪詢一直失敗」的下一步會說錯）。
- **量測**（`scripts/experiments/sweep_loop_lag.py` 加帳本、作品快照、Feed；400 個 Series 全有洞、一半撞集）：一開始
  一輪佔住迴圈 6.7 s——撞集連著解析幾百個發佈名（一個 ~15 ms）沒讓出迴圈，加上 `_series_imports` 整份組 ORM 物件
  ~200 ms。改成只選欄位、500 列一批組，解析一筆讓一次，缺集只對有候選洞的作品問 `read_holdings`：暖機後一輪最長
  16–84 ms（門檻 100 ms），一輪 15 s。**行程裡第一次解析發佈名多 ~400 ms**（guessit 初始化）；規劃器第一次規劃同樣
  付，歸 M4 票 13b 那一條（解析 CPU 在迴圈上），沒處理。
- **code-review 沒處理的**：
  - 補漏裡 `_read_season` 以外的非預期例外（`_backfill` / `_record`）冒到 `poll_due`，由 `_note_failure` 記成輪詢失敗
    （Spec，輕微）：沒有 repro；要分開得在 `_backfill_due` 包一層，動到票 126 也在改的 `rss.py`。
  - 第 3 點「動作是到作品頁搜那幾集」做成連到作品頁＋下一步文字，不是一顆直接帶著集數去搜的按鈕（Spec）：作品頁的
    「搜這部作品缺的集」就是那一顆，搜的正是這幾集（`missing`），與票 129 的形狀一致。
  - 前兩個 commit 的文件（plan 欄位表、CHANGELOG、CONTEXT 的 Issue 型別數）到第三個 commit 才補上（Standards）：
    最後的狀態是對的，本地歷史沒有改寫。
  - `sweep` 三項偵測的收尾（`record_issue` 迴圈＋`_settle`）形狀相近、`_series_imports` 每輪跑兩次、`(error, since)`
    兩對欄位與 `_note_poll` / `_note_backfill` 一樣（Standards，Duplicated Code / Data Clumps）：少動 `rss.py` 與
    結構，量過不影響迴圈。
  - `IssueRow.tsx` 又抄了一份 `INLINE_LINK` 的 class（Standards）：同一串在 `JobLink`、`SearchResults`、
    `SubmitAction` 已各有一份，抽共用元件留給 M4 UI 收尾。
  - `Job.trigger_ref` 對 Series id 的 join 多了兩處（`sweep`；`first_batch`、`review` 原本就有）。
