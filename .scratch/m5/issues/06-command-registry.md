# 06 — 命令登錄表：逐條登記的工具

**Status:** done

**Blocked by:** 04

**讀:** plan §11.6〈命令登錄表〉〈對話核心〉、§1.3、§6；brief §6.10「外部文字是資料」、§14；CONTEXT.md 的 Command Registry、Result Card；`api/gate.py` 的角色檢查；參考 `backup/m5-attempt-1-20261024` 的 `1804888`（第一次的登錄表）

## 為什麼

側面板、M6 的背景任務與 M7 的 MCP server 都只從登錄表拿工具。2026-10-24 拆票時定了**工具逐條登記**：命令都標副作用，但只有明確登記的才是工具。這張先做登錄表本身，加上第一個真的工具，後面每張票只要登記自己的工具。

## 做什麼

先跑 `mattpocock-skills:codebase-design`，定下登錄表的邊界再動手。

1. **一條登記**：工具名、給模型看的說明（英文，進固定的 prompt 前綴）、pydantic 輸入、**結果型別**、需要的角色、怎麼呼叫底下的 service 命令。副作用等級與反向命令直接讀命令的標記，不另寫一份；登記到沒標的命令就紅。
2. **統一拒絕**：各模組自己的例外（`IssueRejectedError`、`PlanRejectedError`…）在登錄表這一層轉成一種拒絕，帶理由碼與「重試 / 交給人 / 放棄」，AI 才分得出下一步。模組的例外不改。
3. **依角色過濾**：給一個使用者的工具清單＝登錄表裡他的角色碰得到的那些，檢查與 API 是同一道（`api/gate.py` 的邏輯，不在模型這邊另做一份）。
4. **actor**：AI 代誰做的要看得出來，AI 活動頁（票 21）要從這裡撈。看現有 `actor: str` 的寫法再定格式，寫進 plan §11.6。
5. **結果型別匯出給前端**：讓前端拿到有型別的結果（走現有的 OpenAPI 產生流程），票 11 依它畫卡。
6. **結果裡沒有帳密**：結果型別不得含 API key、密碼、token 欄位，加一道測試掃全部登記。
7. **第一個工具**：`read` 的「最近入庫」（一段時間內入庫了哪些作品與集），給票 11 的 tracer 用。

## 驗收

- [x] 登記沒標副作用的命令會紅；工具的等級與命令的標記一致（pytest）
- [x] `user` 拿到的工具清單沒有管理員命令，與 API 門禁同一道（pytest）
- [x] 各模組的拒絕例外經登錄表變成統一拒絕，帶下一步（pytest）
- [x] 掃描測試擋下含帳密欄位的結果型別（雙向變異）
- [x] 「最近入庫」可以經登錄表呼叫，結果型別出現在前端的產生型別裡
- [x] 全部檢查、pytest、vitest 綠；plan §11.6、CONTEXT.md、progress.md 已更新

## Comments

- **設計**（codebase-design）：沿用第一次嘗試（`1804888`）的 seam。呼叫端只學 `Registry.tools_for(role)` 與
  `Registry.invoke(name, arguments, context)`；機制在 `services/registry.py`，登記在 `services/tools.py`。「需要的角色」
  不另寫，**登記寫做同一件事的那一支端點** `(方法, 路徑)`，角色照門禁的同一張表（`services/access.py`，從 `api/gate.py`
  搬下來，`admits` 兩邊共用）。代價：沒有對應端點的命令登記不了（brief §14 API-first）。
- **actor** 定成 `ai:<user id>`（`jobs.ai_actor`，plan §2.3）；`claims` 只認純數字的解析改用 `jobs.user_of`，`ai:7` 仍歸到
  使用者 7。M6 的背景任務沒有使用者，到時另定。
- **`ToolRefusal`（`unknown_tool`、`invalid_input`）不放 `domain/enums.py`**：那裡的 `*Refusal` 每一個都要一張狀態碼表
  （`TestStatusTables`），這兩種沒有端點；照樣進 OpenAPI。
- **`recent_imports` 只有管理員**（指著 `GET /weekly`）：一般使用者的版本要先決定他在 Jellyfin 看不到的作品怎麼辦
  （M1.5 的媒體庫權限）。**票 11 的 tracer 要用管理員跑**；`user` 問會得到 `unknown_tool`。
- code-review 已處理：`api/gate.py` docstring 的票號。
- code-review 未處理（判斷題）：
  - `Refusal.detail` 原樣取自模組例外的 `detail`；掃描只看結果型別的欄位名。各模組的 detail 本來就經 API 回給瀏覽器
    （同一份字串），沒看到放憑證的；之後登記會丟 `NotifyRefusedError` 這類帶 `str(exc)` 的命令時要再看一次。
  - `Refusal.reason` 是 `str`，前端產生的型別是 `string` 不是 union；票 11 畫卡若要窮舉再收窄。
  - `REJECTIONS` 只收建構時帶 `reason` 的例外；`ReportMissingError`、`ItemNotVisibleError` 這類「找不到」會當 bug 丟出去。
    登記會丟它們的命令時再加並決定 `next`。沒有共同基底，`reason` / `detail` 用 `getattr` 與一個附理由的 `type: ignore`
    取（票面說模組的例外不改）。
  - 「等級與標記一致」在建構上就成立（`Tool.effect` 讀標記）；`run` 實際呼叫的是不是 `command=` 那一支沒有檢查，等寫入
    工具（票 12、14）的形狀出來再看要不要改成登錄表替 `run` 呼叫命令。
  - `RecentWork` 與 `api/weekly.ImportedWorkOut` 同形：services 不能 import api；`api/weekly` 反過來用 `RecentWork` 會改掉
    前端週報頁的型別名，不在這張票做。
  - `Registry.invoke` 是 services 裡公開的 `async def` 方法，沒標 `@command`：它是分派器，`test_command_marks` 只掃模組層級
    的函式，規則的字面沒寫「方法除外」。
  - CONTEXT.md 沒為 `Tool`、`Refusal`、`NextStep` 開詞條（它們是 Command Registry 詞條裡的「一條登記」「拒絕」「下一步」）。
  - `gate._admin_verdict` 與 `_setup_verdict` 的角色判斷可以收成 `admits`，沒動。
