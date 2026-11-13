# 04 — 卡住的三種 Job 開 Issue

**Status:** ready-for-agent

**Blocked by:** 01

**讀:** spec〈範圍〉〈卡住而沒有 Issue 的三種 Job 開 Issue〉、〈共同規則〉；ADR 0016；plan §2.4、§3.1〈送單失敗的暫時與否〉〈自動重送〉、§3.2〈`sweeper`〉；brief §9.1；`docs/research/m5-ai-direction-2026-10-27.md` C1 表「停住的 Job」那一列；`GLOSSARY.md`〈巡檢〉〈Issue〉

## 為什麼

重試用完的 `submit_failed`、`import_failed`、`stalled` 的 Job 現在沒有 Issue，不會進「等你處理」，只有訂閱的作品會被 M5.5 的遲到提醒間接抓到。這是交給人的出口，M6 的 AI 任務交不出去的事也要有地方放，所以排在 AI 任務之前。

## 做什麼

1. 三種新的 `IssueType`（名稱照 `GLOSSARY.md`，新名詞補進去）：`subject` 取哪一欄、有哪些動作（重試、recheck、刪 Job 這類；照 C1 表那一列，刪 Job 與移除 torrent 留給人），`SUBJECT_OF` 與 `ISSUE_ACTIONS` 兩條閘門跟著改。
2. 誰開、何時開：`submit_failed` 在自動重送用完時；`import_failed` 在進那個狀態時；`stalled` 停多久才算卡住（參考 `sweep.STUCK_AFTER`），在票內定並寫進 Comments。Job 走開了（重試成功、被刪）由系統收掉。
3. 跟 `episodes_overdue` 的關係：卡住的那一集已經有這幾種 Issue 管著時，遲到提醒不再為同一筆另開；`first_batch_stuck` 也照同一條（已有 Issue 管著就不開）。
4. 進「等你處理」與「有 N 件等你處理」的通知；Issue 頁有這三種的文案（zh-Hant 與 en）與按鈕。
5. 文件：plan §2.4、§3.2、brief §9.1、`GLOSSARY.md`。

## 驗收

- [ ] 三種 Job 各開一件 Issue，進「等你處理」；Job 走開了系統收掉（整合測試）
- [ ] 同一筆不再另開 `episodes_overdue`（整合測試）
- [ ] Issue 頁顯示與按鈕可用（vitest；playwright 實跑一次，附截圖）
- [ ] 全部檢查、pytest、vitest 綠

## Comments
