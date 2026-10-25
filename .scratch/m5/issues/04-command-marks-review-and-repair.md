# 04 — 命令標記補齊（一）：審核、修正、入庫與 Job

**Status:** ready-for-agent

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

- [ ] 上列模組從 `BEFORE_M3` 拿掉，`test_command_marks` 綠
- [ ] 三條錯標改掉，各有一條測試說明它為什麼是這個等級
- [ ] `asynccontextmanager` 包過的命令被守（雙向變異）
- [ ] 全部檢查、pytest 綠；progress.md 已更新
