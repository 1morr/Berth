# 01b — 核准卡片的整合測試偶發紅燈

**Status:** ready-for-agent

**Blocked by:** None (can start immediately)

**讀:** `tests/integration/test_proposals_api.py`（`TestDecide`）；`berth/services/proposals.py`（`decide`、`execute`）；`berth/services/importer.py`（`import failed` 那條 log 的來源）；plan §2.6、§3.2（Proposal 與狀態機）；skill `mattpocock-skills:diagnosing-bugs`

## 為什麼

協調者插的修復票（2026-11-04）。同一條測試在 CI 紅了兩次，兩次都跟當時推上去的改動無關：

- 2026-10-30 run 41015905247（c748bff）
- 2026-11-04 run 41676956585（7ec5388d，票 01 的合併；01 只動 AI 設定）

```
FAILED tests/integration/test_proposals_api.py::TestDecide::test_approving_runs_it_and_answers_with_each_rows_result
assert <JobState.IMPORT_FAILED: 'import_failed'> is <JobState.IMPORTING: 'importing'>
WARNING berth.services.importer job import failed  job=cccc…  state=import_failed
        error="this job has no import plan or route any more"
1 failed, 5328 passed（pytest -n auto）
```

回應本身是 `executed`、那一列 `importing`，但測試接著讀資料庫時 Job 已經被某個背景的入庫流程推進成 `import_failed`。看起來是核准後的入庫在背景跑，跟測試的斷言賽跑；本機多半跑得比較快或比較慢所以沒碰到。這是推測，要先證實。

## 做什麼

1. **先分清是產品的問題還是測試的問題**：核准後真的會有一支背景的入庫去動這個 Job 嗎？它在正式環境會不會因為同樣的原因把剛核准的 Job 打成 `import_failed`（「no import plan or route any more」在正式環境是不是也可能發生）？把結論寫在 Comments。
2. **寫出會紅的 repro**：讓賽跑必定發生（例如在斷言前讓出事件迴圈、等背景工作跑完，或固定 xdist 的順序），在修之前穩定紅。
3. 依結論修：
   - 產品的問題：修產品，測試照原本的意圖斷言。
   - 測試的問題：讓測試的 fixture 不觸發背景入庫，或明確等它、斷言它該有的終態；說得出為什麼原本的斷言不成立。
   - **只拉長逾時或加重試、說不出原因的不收。**
4. 修完用 `pytest -n auto` 跑這個檔至少 30 次（或等價的壓力跑法），貼次數與結果。

## 驗收

- [ ] Comments 寫清楚原因，以及它是產品還是測試的問題
- [ ] 有一個在修之前穩定紅、修之後綠的 repro（測試或指令，貼輸出）
- [ ] 壓力跑 30 次以上全綠（貼次數）
- [ ] 全部檢查、pytest 綠；progress.md 已更新
- [ ] 合併後 main 的 CI 綠，補上票 01 被卡住的 CI 驗收（協調者在 ledger 補記）
