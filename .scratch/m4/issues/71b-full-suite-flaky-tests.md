# 71b — 全套 pytest 才會紅、單跑就過的測試：找出根因

**Status:** done

**Blocked by:** 71（使用者決定排在 0.2.1 發版之後，2026-10-09）

**讀:** `docs/development.md`〈全部檢查〉與測試段；`tests/conftest.py` 與 integration 的 fixture；下面三次出現的紀錄（票 59、55、70 的 Comments 與 progress.md 2026-10-08～09）

## 為什麼

同一類紅燈在三張票各出現一次，都只有跑全套才紅，單跑、整檔重跑、再跑一次全套都會過。三張票都沒改到那些測試或它們測的程式：

| 票 | 測試 | 現象 |
| --- | --- | --- |
| 59（rebase 後） | `tests/integration/test_setup_api.py::TestQbittorrent::test_applying_writes_only_the_login` | setup 階段 error，沒留 traceback |
| 55（收尾） | `test_rss_api` 的 `preview_then_follow_from_now` | failed，單跑 3/3 過 |
| 70（rebase 後） | `tests/integration/test_setup_api.py::TestGate::test_after_the_owner_the_same_writes_need_a_session[POST-/api/setup/qbittorrent/apply-None]` | failed，單跑 TestGate 3×38 過，再跑全套過 |

這類偶發會讓每張票的驗收多跑一輪全套（約 12 分鐘），也讓真的紅燈被當成「又是偶發」放過。

## 做什麼

1. 用 `mattpocock-skills:diagnosing-bugs`。**先分清是產品的問題還是測試的問題**（共用狀態、順序依賴、時間或時鐘、port、背景工作沒收乾淨、資料庫或檔案沒隔離），不要先猜。
2. **先做出會紅的 repro**：
   - 例如固定 `-p randomly` 的 seed、只跑造成干擾的那幾個檔案的組合、或 `--count` 重複；
   - 寫成一條指令或一支腳本，失敗率要量出來（N 次裡紅幾次）。
3. 修根因，修完用同一個 repro 證明失敗率歸零（同樣的 N 次）。
4. **只拉長逾時、加 retry、加 sleep，而說不出原因的修法不收。**
5. 原因如果在產品程式（不是測試），照 tdd 補一條會紅的測試。

## 驗收

- [x] 寫明根因（是產品還是測試、哪個共用狀態或順序），附 repro 指令與修前失敗率
- [x] 修後同一個 repro 失敗率 0（次數與修前相同），附輸出
- [x] 三條測試都在根因的解釋範圍內；有不在範圍內的，另開票並寫明
- [x] 全部檢查、pytest 全套綠；progress.md 記一行

## 根因（2026-10-09）

**產品的問題，測試只是把它變成紅燈。** lifespan 關機時 cancel 七個背景迴圈（`main.py`）。cancel 落在某個迴圈剛建好一條連線、SQLAlchemy 還在跑方言 `connect` handler（aiosqlite 的兩次 `create_function`，都要 await worker thread）的那一段時，`_ConnectionRecord.__connect` 把例外往上丟、不關那條 DBAPI 連線（async 下 IO 半途被 cancel 是 SQLAlchemy 不支援的，sqlalchemy#8145；`db/engine.py` 的 shield 只蓋到建連線與 pragma，蓋不到交回 pool 之後這一段）。那條 aiosqlite 連線要等 GC 才 `ResourceWarning`；pytest 的 unraisable plugin 在**當時正在跑的那一條**測試的 setup / call / teardown 收它，`filterwarnings = error` 底下就是那一條的 error 或 failed。共用的不是資料或順序，是「上一個 TestClient 留下的垃圾什麼時候被 GC」。全套才會紅：迴圈第一次醒來（qbit poller 5 秒）要剛好撞上測試結束，單跑的測試多半在那之前就收了。

**Repro**：`uv run pytest scripts/experiments/loop_shutdown_leak.py -q -p no:cacheprovider -s`（每個迴圈的間隔壓到 1 ms、反覆啟停 app 100 次、每次 GC，數洩漏的輪數）。

| | 6 次裡紅幾次 | 600 次啟停裡洩漏幾次 |
| --- | --- | --- |
| 修前（`0f28d48` 的 worktree，與 `a303406` 只差 README） | 6 | 10（每次 1–3） |
| 修後 | 0 | 0 |

洩漏的連線來自六個迴圈（importer、planner_runner、qbit_poller、health_checker、jellyfin_resolver、rss_poller）；reconciler 沒到 04:00 不碰資料庫，探針裡碰不到，regression test 讓它跨過 04:00 一樣紅。**證偽**：同一支探針把方言的 `on_connect` 換成 no-op，600 次 0 次（基準 17 次）；洩漏的連線全都沒走到 pool 的 `connect` 事件。

**修法**：`pipeline/ticks.py` 的 `whole_tick`——一輪跑到一半被 cancel 時先讓它做完再把 cancel 往上傳（第二次 cancel 也不打斷），七個迴圈的 `run()` 都包上。regression test `tests/integration/test_loop_shutdown.py` 在 pool 的 `connect` handler 裡停住、cancel 迴圈一次或兩次，斷言每一條開過的連線都被關掉：修前 7 個迴圈全紅；拿掉其中一個迴圈的包裝只有它紅；把第二次 cancel 的保護拿掉只有 `-2` 那 7 條紅。不是拉長逾時、retry 或 sleep。

**三條測試**：都在解釋範圍內，但是**旁證**——當時沒留輸出，這次全套（修前 3695 passed）也沒有自然撞到。對得上的是形狀：受害的是「GC 剛好發生時正在跑的那一條」，與它測什麼無關；票 59 是 setup 階段 error（`TestQbittorrent` 的 `client` fixture 起 app、`_claim`），票 70 與票 55 是 call 階段 failed。票 55 記的「全套負載下的時序不穩」站不住：`test_preview_then_follow_from_now` 沒有時間相關的斷言。

## Comments

- code-review（Standards）：**七個 `run()` 長得一樣**（等待 → `whole_tick` → `except Exception` 記 log），可以收成一個骨架。這次沒做：骨架各自的等待不同（sleep、提示、模組常數），收起來要動七個建構子與它們的測試；`test_every_loop_is_here` 加參數化的 cancel 測試已經擋住「新迴圈忘了包」。
- code-review（Spec）：**對帳的 task（`ReconcileRunner._task`，每日 04:00 或 `POST /reconcile` 開的）關機時仍直接 cancel**，同一種洩漏理論上也會發生。不在這張：一輪對帳要掃整個磁碟，關機等它做完不合理；原本的設計就是「跑到一半被收掉的那一輪不留半筆」。要處理得讓對帳在 IO 之間自己看停止旗標，失效條件寫得出來再開票。
- 關機要等正在跑的那一輪做完，**沒有總上限**（理由與代價寫在 `pipeline/ticks.py` 開頭、progress.md 偏差與決定）。
