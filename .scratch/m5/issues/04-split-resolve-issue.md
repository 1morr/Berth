# 04 — 拆開 `issues.resolve_issue`：一種動作一個命令

**Status:** ready-for-agent

**Blocked by:** 02

**讀:** plan §11.6〈分段〉第 1 段；`docs/research/m5-ai-direction-2026-10-27.md` A3 的 R8、A5 的 B3、C1 的 Issue 那兩列；`berth/services/issues.py`；`berth/domain/enums.py` 的 `ISSUE_ACTIONS`、`ACTION_DELETES`；`berth/api/issues.py`

## 為什麼

一個函式吞了 17 種 `IssueAction`，可逆性差很多：有重新鏈接、recheck，也有刪 complete、刪孤兒目錄。只有一個標記，登錄表與確認卡就分不出哪些要人。

## 做什麼

1. 每一種 `IssueAction` 一個命令函式，各自標記。刪東西的標 `IRREVERSIBLE`，「忽略」類也要人（brief §14：藏起問題）。
2. 共用的前置與收尾（找 Issue、檢查狀態、記事件、收掉 Issue）抽成私有函式，不在每個命令裡重寫。
3. **API 形狀不變**：`POST /issues/{id}/resolve` 照 `action` 分派到對應的命令，前端不用改。分派表與 `ISSUE_ACTIONS` 對得上，用測試守。
4. 從豁免表移掉 `issues`（`resolve_issue` 以外的命令由票 03 標）。

## 驗收

- [ ] 每一種 action 都有自己的命令與標記；`ACTION_DELETES` 裡的都是 `IRREVERSIBLE`
- [ ] 分派表與 `ISSUE_ACTIONS` 一一對應（測試）
- [ ] 現有的 Issue 測試不改行為照樣綠
- [ ] 全部檢查與 pytest 綠；progress.md 已更新

## Comments

- 2026-10-27（票 03 留）：`issues` 已經不在豁免表（做什麼第 4 條已完成）。`resolve_issue` 暫標 `IRREVERSIBLE`，拆開時換成各動作自己的標記；`issues.ignore_issue` 標 `IRREVERSIBLE`（沒有收回忽略的命令，brief §14 要人），拆「忽略」類時一起看。
