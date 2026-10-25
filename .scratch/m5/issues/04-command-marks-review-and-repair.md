# 04 — 命令標記補齊（一）：審核、修正、入庫與 Job

**Status:** done

**Blocked by:** None — can start immediately

**讀:** plan §11.6〈命令登錄表〉、§11.5（`asynccontextmanager` 那一條）；brief §14「自主權看可不可以撤銷」；`berth/services/commands.py` 與 `tests/unit/test_command_marks.py` 的 docstring；M3 票 05

## 為什麼

M5 的登錄表讀每個命令的副作用標記；M6 的接管開關靠它分出「AI 自己做」與「做成 Proposal」。`BEFORE_M3` 豁免表還有 41 個模組沒標，其中人工按鈕所在的那一半，剛好是 M6 最先要交給 AI 的。標錯的比沒標更危險：錯標成可逆的不可逆命令，會讓 AI 不經人就做。

## 做什麼

1. 標完這些模組裡的公開命令，標完就從 `BEFORE_M3` 拿掉：`claims`、`complete`、`deletion`、`duplicates`、`health_issues`、`importer`、`inventory`、`issues`、`jobs`、`media`、`plan`、`plan_review`、`plan_view`、`reconcile`、`reimport`、`rematch`、`resolver`、`resolve_schedule`（約 73 個）。判不出等級的寫進票的 Comments，不要猜。
2. 包括 M3 後加進舊模組、會改狀態卻沒標的：`jobs.fail_interrupted`、`issues.close_settled`、`resolver.settle_verdicts`。
3. 改掉標錯的三條：
   - `review.confirm_audit(s)` 的反向命令 `review.undo_audit` 語意對不上（它拆入庫，而且拒絕確認過的列）：另立「取消確認」，或改成 `inverse=None`。
   - `rss.delete_feed` 連帶刪掉 Feed Item（CASCADE），卻標成可逆、反向是 `add_feed`：照實標。
   - `rss.poll_due` 是背景迴圈入口：照它實際的副作用標。工具改成逐條登記之後（plan §11.6），它不會變成工具，只要標得誠實。
4. `test_command_marks` 看得到被 `asynccontextmanager` 包過的公開命令。雙向變異照舊：包一層 contextmanager 又拿掉標記會紅。

## 驗收

- [x] 上列模組從 `BEFORE_M3` 拿掉，`test_command_marks` 綠
- [x] 三條錯標改掉，各有一條測試說明它為什麼是這個等級
- [x] `asynccontextmanager` 包過的命令被守（雙向變異）
- [x] 全部檢查、pytest 綠；progress.md 已更新

## Comments

- 等級全部判得出來，沒有留白。`confirm_audit(s)` 選 `inverse=None`（不另立「取消確認」）：確認只清旗標、檔案不動，放錯了照樣 rematch 或刪；回不去的只有「等人看」這個狀態。
- **標法的慣例寫進 `berth/services/commands.py` 的 docstring**（人按的照主效果、背景迴圈的入口照最重的、多動作的照最重的那一種），是把 M4 的 `add_manual_download` 與 `sweep_once` 兩個先例統一說清楚，不是新規則。code-review 兩軸都質疑「主效果」那一半：`rss.poll_feed`（人按的單一 Feed 輪詢）會送單、排「正在下載」卻標 `reversible`，`resolver.resolve_early` 同樣會排「可以看了」。後者已改註解說明它排的是排程那一輪稍後也會排的同一則；前者留給票 06 登記工具時決定（它若成為 AI 的工具，要嘛改標、要嘛登錄表另擋）。測試不鎖 `poll_feed` 的等級。
- `health_issues.set_min_free` 照 repo 先例（`rss.set_exclusions`、`notify.set_*`）標 `reversible`、反向是自己。brief §14 把「改設定與 Route」列為永遠要人：這條界線由登錄表的逐條登記擋（不登記成工具或登記時要確認），還是改標記，票 05 標 `settings` 時一起定。
- `add_feed` 與 `subscribe_search` 的反向指向現在是 `irreversible` 的 `delete_feed`：加完就撤沒損失，輪過幾輪再撤會丟掉累積的 Item。撤銷鍵要不要出確認卡由票 06 / 14 決定。
- `issues.resolve_issue`、`deletion.delete_job` 照最重的動作標 `irreversible`；分動作 / 分旗標的等級是登錄表的事（票 06）。`issues.ignore_issue` 依 brief §14 標 `irreversible`（要人）。
- 內部原語也標了：`jobs.transition`、`record_event`、`guarded`（`reversible`，`guarded` 只接規劃與入庫的一輪，註解寫明交別的進來要重看）、`job_locks` / `rematch.locked`（行程內的鎖，`read`）。它們不會被登記成工具。
- 沒處理：`jobs.job_lock` 是公開的同步 `def`、回傳 async context manager，檢查看不到它（不在票面「被 `asynccontextmanager` 包過的」範圍）；它是鎖，沒有狀態副作用。
- `READ` 的定義補上「寫回外部資料的快取（TMDB 快照）也算只讀」，`media.*` 與 `claims.ensure_media` 照它標。
