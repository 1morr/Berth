# 03 — 卡住的 Job 開成 Issue

**Status:** ready-for-agent

**Blocked by:** None — can start immediately

**讀:** plan §11.5「2026-10-24 已定」那一條、§2.4、§3.1、§3.2（`reconciler` / 巡檢的排程）；brief §9.1、§19 2026-10-24「AI 不設預算、接管開關、側面板提前」第④條；M4 票 129 的做法與 Comments；`IssueType` 的 docstring（加型別要過 `SUBJECT_OF` 與 `ISSUE_ACTIONS` 兩道閘門）

## 為什麼

M4 票 129 只把卡住的 Job 放在下載頁「需要人」的篩選與 Job 頁上，沒有開 Issue。M6 的接管開關只看得到 Issue、審核與待綁定這三份清單，所以卡住的 Job 要先變成 Issue，AI 才碰得到。這件事本身不需要 AI，也讓人在「等你處理」與推播裡看得到它們。

## 做什麼

1. 新的 Issue 型別涵蓋三種卡住：重試用完的 `submit_failed`、永久失敗的 `import_failed`、`stalled`。一種型別一個，還是一種型別帶原因，照 `IssueType` 既有的取捨定，並寫進 plan §2.4。
2. 每一種給齊 `SUBJECT_OF` 與 `ISSUE_ACTIONS`：可用的動作沿用 Job 頁已有的那幾顆（retry、resubmit、放棄……），不另發明。
3. 開與關：誰開（巡檢或 Job 轉狀態的那一刻，二選一，理由寫進票）、冪等鍵、Job 被救回來之後 Issue 自動收掉（照 `close_settled` 的路）。
4. 算進「等你處理」的數字與推播（M4 的通知），通知文案走 i18n，zh-Hant 與 en 並列。
5. 下載頁「需要人」的篩選與 Job 頁的提示，改從 Issue 來或保持現狀但不重複計數，二選一並說明。

## 驗收

- [ ] 三種卡住各自開出一筆 Issue，同一個 Job 不重複開（pytest）
- [ ] Job 重試成功或被放棄後，Issue 收掉（pytest）
- [ ] Issue 頁看得到、按得到動作；「等你處理」計數與推播都算進去（pytest＋vitest，UI 用 playwright 實跑）
- [ ] `SUBJECT_OF`、`ISSUE_ACTIONS` 的閘門綠
- [ ] 全部檢查、pytest、vitest 綠；plan §2.4、CHANGELOG、progress.md 已更新
