# 10 — 遲到判定與 `episodes_overdue`

**Status:** ready-for-agent

**Blocked by:** None (can start immediately)

**讀:** spec〈範圍〉「遲到判定」「提醒」；brief §9.1（Issue 表）、§20.12；plan §2.4、§3.1；`services/sweep.py`（`_covered`、`_missing_episodes`、`_settle`）；`services/why_not.py`（`_job_claims`）；skill `mattpocock-skills:tdd`

## 為什麼

看得出訂閱的作品有沒有按時入庫：播出滿兩天沒入庫就開一件 Issue，說得出卡在哪，已經在等你處理的不重複開。這張先跑通最基本的「晚了」（`reason = late`）；換輪、60 天視窗、單一 Series 的門檻與巡檢前刷新在 11。

## 做什麼

1. **純函式 `parser/overdue.py`**，一部作品一個結果：
   - 對象：有綁好的 RSS Series 的作品；第 0 季不看；季集用 TMDB 編號（帳本本來就是）。
   - 基準：作品最後入庫的一集，不分來源；還沒入庫過時，從作品最早的 RSS Series 的 `created_at` 之後播出的第一集算。
   - 缺的：基準之後已到播出日、還沒入庫的集。中間的洞仍歸 `series_episodes_missing`（`_missing_episodes` 不看的那一段才是這裡的）。
   - 晚：從播出日隔天 00:00（容器 `TZ`）起算滿門檻。門檻預設 2 天，設定頁可改（這張只做全域設定）。例：10/28 播出，10/31 05:00 巡檢才開。
   - 例外只有兩種：**下載還在動**（蓋到它的 Job 在 `UNDER_WAY_STATES`，`stalled` 不算）、**已經在等你處理**（Job 是 `review`，或 Job 有開著或被忽略、說著它現在這個狀態的 Issue：`missing_files`、`client_error`、`client_removed`，查法同 `sweep._covered`）。M6 的三種 Issue 開了也走這一條。
   - 卡在哪：字幕組沒發、送單失敗、下載停滯、入庫失敗。每一集蓋到哪些 Job 用 `why_not._job_claims` 那一份（`read_holdings` 分不出來）。
   - **不讀 `series_finished`**。
2. **Issue 型別 `episodes_overdue`**：每日巡檢開，條件解除時系統收掉，一部作品一件（`IssueSubject` 新增作品）。
   - `detail_json` 帶 `reason`（這張只有 `late`，`next_run` 留給 11，但格式先容得下）、作品名、缺的集、卡在哪。
   - 下一步：搜這一集或去訂閱（連 Media 詳情）、處理卡住的 Job（連 `/jobs/{hash}`）、忽略（條件持續期間有效）。
   - Issue 頁畫得出來（zh-Hant、en）。
3. 文件：brief §9.1 的 Issue 表、plan §2.4、`CONTEXT.md`（遲到、Issue 種數）。

## 驗收

- [ ] 訂閱的作品 10/28 播出而字幕組沒發：10/30 不開，10/31 巡檢開一件，發了入庫後系統收掉（測試）
- [ ] 另一個字幕組或手動下載已入庫那一集時不開（測試）
- [ ] 過了門檻的集，下載停滯或入庫失敗時開一件並說出卡在哪，入庫後系統收掉（測試）
- [ ] 下載還在動、等審核、Job 有開著或被忽略的 Issue 時不開；那件 Issue 收掉而這一集還缺時，下一輪開（測試）
- [ ] `series_finished` 為真而 TMDB 有最近播出、未入庫的集時仍開（守「不讀」的測試）
- [ ] Issue 頁顯示作品名、缺的集、卡在哪與三個下一步（playwright 實跑）
- [ ] 全部檢查、pytest、vitest 綠；progress.md 已更新
