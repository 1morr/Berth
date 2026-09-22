# 01 — 開工收尾（後端）

**Status:** done

**Blocked by:** 無 —— 可立即開工

**讀:** plan §3.2（`qbit_poller` 那一列與底下關於它的三條）、§6（jobs 群組）、§11.3（票 01 那一列）；brief §20.2

## 做什麼

M2 開工前把五件有 repro、不需要新載體的後端債清掉。它們互相獨立，順序隨意。

1. **兩個會 500 的路徑**。
   - 同一個新使用者**兩次登入同時進來**撞 `users.jellyfin_user_id` 的 unique：`services/auth.py`
     的 `_mirror_user` 沒接 `IntegrityError`。兩條都該拿到同一個鏡像使用者。
   - `check_routes` **跑到一半 Route 被刪**：`api/setup.py` 只接 `ValueError`，SQLAlchemy 的
     `StaleDataError` 裸奔成 500。它該是 plan §6 已經定好的 404 `route_missing`（票 14、14a
     對 `routes/*` 定的同一種拒絕）。
2. **`Season 3 / … Season 3 - 46` 被讀成 `S03E03–E46`**。`berth/parser/release.py` 的
   `_LOOSE_RANGE`（行 67、用在行 217）把 `Season 3 - 46` 這種「季號 - 集號」當成集數範圍。
   走 tdd：先把這一類加進自己的語料 fixture（紅燈），再改規則。改完跑一輪 `berth bench`，
   `auto_wrong` 不得上升（專案 CLAUDE.md 的架構規則）。
3. **`list_jobs` 逐列查詢改批次**。`services/jobs.py:394`，每一筆 job 各查一次關聯，清單長了
   就是 N+1。
4. **`QbitPoller` 補整合測試**。五個背景迴圈裡唯一沒有的，而它扛著 §3.2 那三條實跑換來的規則：
   醒得比問頻繁且間隔每次醒來重算、HTTP client 握著不放（`rid` 增量掛在那條連線上）、推播在
   commit 之後。
5. **兩個沒人引用的 fixture**：`tests/fixtures/http/jellyfin/useritems-resume.restricted.json`
   與 `shows-nextup.restricted.json`（M1.5 票 01 錄的）。補上引用它們的測試，或刪掉——留著
   沒有測試看管的 fixture 會在下一次換版本時被當成還有效的證據。

## 驗收

- [x] 兩個 500 各有一個先紅後綠的測試：併發登入拿到同一個鏡像使用者；檢查途中 Route 被刪回
      404 `route_missing` 而不是 500
- [x] `Season 3 - 46` 這一類在語料裡有 fixture，`berth bench` 綠燈且 `auto_wrong` 沒有上升
      （貼改動前後兩次的數字）
- [x] `list_jobs` 的查詢次數不隨 job 數成長（以查詢計數斷言，不是靠計時）
- [x] `QbitPoller` 的整合測試涵蓋 §3.2 那三條規則，每一條的變異（把規則改回去）都會讓它紅
- [x] 兩個 restricted fixture 要嘛有測試引用、要嘛刪掉
- [x] lint、type、test 綠燈（貼指令輸出）

### 驗收的輸出

**`berth bench`**（語料 32 → 34 筆、385 → 387 個檔案）：

| 時點 | auto_correct | auto_wrong | review |
| --- | --- | --- | --- |
| 改動前（舊語料） | 172 | 0 | 79 |
| 加了兩筆 fixture、還沒改規則 | 172 | **2** | 79 |
| 改完規則 | 172 | **0** | 81 |

加進來的兩筆改規則前是 **high 信心自動入庫成 S03E04**（`bench: auto_wrong rose from 0 to 2`），
改完落在 `review`。`baseline.json` 因此不必動。

**`QbitPoller` 三條規則的變異驗證**（改回去 → 紅）：

| 規則 | 變異 | 變紅的測試 |
| --- | --- | --- |
| 間隔每次醒來重算 | `tick()` 快取第一次算出來的 `wait` | `test_the_interval_is_recomputed_on_every_wake` |
| client 握著不放 | `Downloader._connect` 拿掉重用那一段 | `test_the_same_client_carries_every_round`、`test_a_failed_round_drops_it_so_the_next_one_starts_over` |
| 推播在 commit 之後 | `poll_downloads` 把 publish 移到 `commit()` 之前 | `test_the_signal_goes_out_after_the_round_is_committed` |

另外 `_mirror_user` 拿掉 `IntegrityError` 那一段 → `test_the_same_first_login_twice_at_once_lands_on_one_row` 紅。

**閘門**：`ruff check` / `ruff format --check` / `mypy`（209 檔）/ `lint-imports`（6 契約）全綠；
`pytest` **1587 passed**（新增 22 條）。

## Comments

review 兩軸（Standards / Spec）處理完之後剩下的，不在這一票做：

- **`services/jobs.py` 的 `_by_id(session, model, key, ids)` 留著 `key` 參數**。Standards 軸標
  Speculative Generality（三個呼叫點都是主鍵）。判斷是留：三個呼叫點是三個不同的 model，
  `key` 是 `where(...)` 與 `getattr` 兩處都要的機制本身，拿掉要改成一個 Protocol，反而更多。
- **`create_route` / `update_route` 外層仍各有一層 `_stale_write_as_missing`**。`_run_checks`
  自己包了之後看起來是雙層，但外層蓋的是它們自己那一次 `commit()`（啟用、改名），不是重複。
  `check_route` 那一層是真的重複，已刪。
- **`test_downloads.py::test_a_failed_round_drops_the_connection_so_the_next_one_starts_over`
  的名字超出它驗得到的範圍**：它驗的是「失敗之後下一輪照樣跑得起來」，連線身分驗不到
  （共用的替身）。連線身分那一條在 `test_qbit_poller.py`。同一組裡那條真的假閘門
  （`test_the_connection_is_reused_across_rounds`）已刪，理由寫在 `TestDownloader` 的 docstring。
- **`QbitPoller` 規則 1 的第一個測試是常數對常數**（`tick_seconds == ACTIVE_INTERVAL`）。
  行為那一半由 `test_it_sleeps_between_ticks` 與 `test_the_interval_is_recomputed_on_every_wake`
  補；Spec 軸認為夠，記在這裡是因為它單看確實只是在覆述常數。
- **`tests/unit/test_fs.py::test_free_space_reports_the_target_file_system` 會偶發**（既有的，
  不是這一票改出來的）。它是 `free_space(tmp_path) == shutil.disk_usage(tmp_path).free`——
  對實時磁碟可用空間做**等值**比較，而兩次量測之間隔著一次函式呼叫。全量跑約四分鐘、期間
  建了上千個暫時 SQLite，這一票的三次全量跑裡紅過一次（單跑與之後兩次全量都綠）。
  失效條件寫得出來（量測之間有別的程序動到那個檔案系統），修法是改成容差比較，不在這一票做。
- **刪掉兩份 restricted fixture 的代價**：brief §20.8「不帶 `parentId` 的 Resume / NextUp 會套
  權限」的實測證物不再留在 repo。判斷是可以接受——同一件事由 `useritems-resume.watching.json`
  與 `shows-nextup.watching.json`（同一輪 12.1.0、同一個受限使用者、項目集合一字不差）守著，
  而那兩份有契約測試引用；`scripts/experiments/jellyfin_permissions.py` 那兩列的 `"filtered"`
  期望也還在，換版本時重跑就重得回來。
