# 03 — 命令標記補齊（一）：審核、修正、入庫與 Job

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

- **使用者在這張決定補守衛**：rematch 的「忽略」（含跟著影片被拿掉的字幕）與 audit 撤銷，在 complete 裡的來源
  不在時會拆掉媒體庫裡唯一一份。補了 `deletion.last_copy`，兩者拒絕（`ReviewRefusal` / `RematchRefusal` 多
  `source_missing`，409，中英文案），之後才照 brief §14 標可逆；rematch 的反向是它自己（`rematch.rematch_file`）。
  重複版本的「取代」不套：它要的就是舊的消失。殘留：來源路徑還在、但已是另一個檔案時 `last_copy` 回 False
  （註解裡刻意接受：重新下載是同一份內容）；更嚴的做法是看媒體庫那一份的 `st_nlink == 1`。
- **一支命令照最壞的標**（brief §14 補一句）：`issues.resolve_issue`、`duplicates.decide_duplicate`、
  `deletion.delete_job` 標 `irreversible`，裡面的「重新反查」「跳過」「保留兩者」等可逆按鈕跟著被擋。M6 要接管
  它們，得先拆成各自的命令（或讓標記能看參數）。`rematch.land` 也是 `irreversible`：守衛在 `rematch_file`。
- **等級的判斷依據**（都照 repo 先例）：人按的命令看主效果（`downloading.add_manual_download`），所以
  `rss.poll_feed`、`resolver.resolve_early` 留在可逆——後者會提早排「可以看了」，那一則 `sweep_resolutions` 下一輪
  本來就會排；背景迴圈排了給人的通知才是不可逆（`poll_due`、`sweep_resolutions`）。`watch_conditions`、
  `reconcile_once`、`flag_stuck_jobs`、`sweep_plans` 只開 Issue 或待審、本身不排通知，標可逆；之後由
  `notify.watch_waiting` 推播的「等你處理」算那一支的（Spec 提醒只在字面上相符，入口都不會變成工具）。
- **brief §14 的「改設定永遠要人」照字面標**：`health_issues.set_min_free` 是 `irreversible`。但既有的
  `notify.set_bot_token` / `set_mine` / `set_berth_url`、`rss.set_feed_interval`、`indexer.set_interface_login`、
  `qbittorrent.set_interface_login` 標 `reversible`，兩種標法不一致——票 04（設定那一半）要定一個。
- **READ 包含補快取**：`media.read_media` 等與 `claims.ensure_media` 會寫 TMDB 快取，`Effect.READ` 的定義補了一句。
- **code-review 未處理的**（判斷題）：
  - 公開 `async def` 一律算命令，所以 `jobs.transition`、`record_event`、`guarded` 與 rematch 的幾個零件也得標
    （Standards：Speculative Generality；Spec：`transition`、`guarded` 的等級其實看呼叫端）。標了 `reversible`
    說明理由；票 04 / 05 可考慮把零件改私有或給零件豁免。
  - 可逆命令的回頭路走的是不可逆命令：`claims.reimport_folder` / `claim_torrent` 回去是 `delete_job`（範圍全不勾），
    `claim_file` 回去是 Issue 的「忘掉」（在 `resolve_issue` 裡）。票 14 的逐筆撤銷遇到它們要出確認卡或拆命令。
  - `last_copy` 的 stat 失敗回報成 `unlink_failed`（「拿不掉，什麼都沒改」），效果上仍正確，沒另立理由。
  - rematch 的 `source_missing` 只有後端測試與型別保證（`ReasonSet`），沒有專門的前端測試；審核頁那一條有。
