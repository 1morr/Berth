# 01b — 核准卡片的整合測試偶發紅燈

**Status:** done

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

- [x] Comments 寫清楚原因，以及它是產品還是測試的問題
- [x] 有一個在修之前穩定紅、修之後綠的 repro（測試或指令，貼輸出）
- [x] 壓力跑 30 次以上全綠（貼次數）
- [x] 全部檢查、pytest 綠；progress.md 已更新
- [ ] 合併後 main 的 CI 綠，補上票 01 被卡住的 CI 驗收（協調者在 ledger 補記）

## Comments

- **原因（已證實）**：核准跑 `jobs.retry_job`，Job 從 `import_failed` 進 `importing`；執行器的 `_after` 看到 `importing` 就叫醒 importer。`TestClient(app)` 會跑 lifespan，九個背景迴圈真的在 portal 的事件迴圈上跑，所以 importer 立刻掃到那一筆。fixture 造的 Job 沒有 Plan、`route_id` 是 `NULL`，`_import` 走 `_fail` → `import_failed`（log 那一句就是它）。測試接著讀資料庫，看到哪一站取決於 importer 那一輪跑完了沒。
- **是測試的問題**：正式環境進得了 `importing` 的 Job 都先由 planner 寫了 Plan（`import_failed` 只從 `importing` 來），Route 被 Job 引用時 `delete_route` 拒絕 `route_in_use`，`plans.job_hash` 只在 Job 刪掉時 cascade。所以剛核准的 Job 不會因為「no import plan or route any more」被打回去；叫醒 importer 是預期的行為（`test_executor.py` 守）。
- **原本的斷言為什麼不成立**：Job 的狀態在核准之後歸 importer 管，不是這個命令的結果。改成斷言命令自己寫的那筆時間線事件 `retried`（`Actor.ai(crew).label`、`{"state": "importing"}`）：它與狀態轉換同一個交易、回應之前已 commit，importer 不改不刪，`RETRIED` 是去重的界線所以也不會被吞。回應那一列的 `importing` 照舊斷言。沒改 fixture 讓它入庫成功（票列的「斷言終態」）：那要造檔案、JobFile 與 PlanItem，測的就變成 importer 了；也沒換掉 `import_hints` 讓它不觸發，importer 還有 60 秒一次的定時掃描。
- **同檔另外兩條一起改**：`test_the_body_takes_no_arguments`、`test_someone_elses_card_is_missing` 原本用「Job 還是 `import_failed`」斷言卡片沒跑，但卡片真的跑了 importer 也會把它打回 `import_failed`，那條斷言抓不到。改成 `retried_events(...) == []`；變異驗證：讓 404 那條改由管理員核准自己的卡，紅在 `assert [('ai:2', {'state': 'importing'})] == []`。
- **repro**：在最後一個斷言前插 `import time; time.sleep(0.5)`（讓 importer 那一輪一定跑完），`uv run pytest -q -p no:randomly tests/integration/test_proposals_api.py::TestDecide::test_approving_runs_it_and_answers_with_each_rows_result` 各跑 10 次：

  ```
  == before fix (orig + sleep)
   failed failed failed failed failed failed failed failed failed failed
  E       AssertionError: assert <JobState.IMPORT_FAILED: 'import_failed'> is <JobState.IMPORTING: 'importing'>
  {"level": "WARNING", "logger": "berth.services.importer", "message": "job import failed", "job": "cccc…", "state": "import_failed", "error": "this job has no import plan or route any more"}
  == after fix (final + sleep)
   passed passed passed passed passed passed passed passed passed passed
  ```
- **壓力跑**：`uv run pytest -q -n auto tests/integration/test_proposals_api.py` 40 次：`runs=40 pass=40 fail=0`。
- **全部檢查**：`uv run pre-commit run --all-files` 全部 Passed；`uv run pytest -q -n auto`：`5386 passed, 1 skipped`。
- **同型的其他測試**：用 `TestClient` 又造 `import_failed` Job 的只有本檔與 `test_agent_slash.py`；後者不核准，不會叫醒 importer。`test_proposals.py`、`test_executor.py` 沒有跑著的迴圈。
- **code-review 未處理的發現**：`retried_events` 的查詢形狀與 `test_executor.py:109` 相同，兩處而已，沒抽共用 helper。
- 最後一條（合併後 main 的 CI）要合併之後才看得到，由協調者補記。
