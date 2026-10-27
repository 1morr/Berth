# 04 — 拆開 `issues.resolve_issue`：一種動作一個命令

**Status:** done

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

- [x] 每一種 action 都有自己的命令與標記；`ACTION_DELETES` 裡的都是 `IRREVERSIBLE`
- [x] 分派表與 `ISSUE_ACTIONS` 一一對應（測試）
- [x] 現有的 Issue 測試不改行為照樣綠
- [x] 全部檢查與 pytest 綠；progress.md 已更新

## Comments

- 2026-10-27（票 03 留）：`issues` 已經不在豁免表（做什麼第 4 條已完成）。`resolve_issue` 暫標 `IRREVERSIBLE`，拆開時換成各動作自己的標記；`issues.ignore_issue` 標 `IRREVERSIBLE`（沒有收回忽略的命令，brief §14 要人），拆「忽略」類時一起看。
- 2026-10-27（實作）：命令名是按鈕值（`issues.relink` …），`adopt` 例外叫 `issues.reimport`（`CONTEXT.md`〈Claim〉禁止函式叫 adopt）。分派表 `BUTTONS` 與 `Press` 放在 `services/issues.py`，API 與測試共用（票面寫「API 照 action 分派」，分派由 API 呼叫）。票 07 把路由搬進執行器時可以改成以命令名分派、拿掉這張表。
- 2026-10-27（實作；合併票 03 後改寫）：`issues` 另外四支非按鈕的命令由票 03 先標、先合進 `main`，這張票各自做出的判斷與它一致：`record_issue`、`close_settled` 是 `reversible` + `internal`，`list_issues` 是 `read`，`ignore_issue` 是 `irreversible`（brief §14：忽略會藏起問題，沒有命令重開；不另立旗標）。合併時拿掉票 03 對 `resolve_issue` 的暫標，`NAMED` 兩邊合起來，另外釘上 `record_issue`、`close_settled`、`list_issues`。
- 2026-10-27（實作，待使用者確認的標法）：`forget`（承認刪除並清帳本）不在 `ACTION_DELETES`、研究 C1 兩列都沒列它，標 `irreversible`：它只 purge 一列帳本，brief §14 把 purge 列在不可逆；來源還在的話重新入庫長得回來，但那是另一條路。`mark_sourceless`、`accept_loss`、`accept_removal` 照 C1 標 `irreversible`。`recheck`、`retry` 不帶 `downloads`（請 qBittorrent 重新開始已有的 torrent，不是送出新的）；`resubmit` 帶。
- 2026-10-27（code-review 未處理）：每個命令把同一個 `IssueAction` 寫兩次（`_pressable` 與 `_settle`），寫成不同值會記錯 `detail_json.action`，目前沒有測試抓；`recheck` / `retry`、`accept_loss` / `accept_removal` 兩對幾乎一樣；加一顆按鈕要改 enum、`ISSUE_ACTIONS`、命令、`BUTTONS`、`NAMED` 五處（以前由 `assert_never` 擋漏接，現在靠 `test_issue_commands`）。都是判斷題，登錄表（票 06）定下命令形狀後再看要不要收。
