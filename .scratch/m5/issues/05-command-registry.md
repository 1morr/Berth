# 05 — 命令登錄表：逐條登記的工具

**Status:** done

**Blocked by:** 03

**讀:** plan §11.6〈命令登錄表〉〈對話核心〉、§1.3、§6；brief §6.10「外部文字是資料」、§14；CONTEXT.md 的 Command Registry、Result Card；`api/gate.py` 的角色檢查

## 為什麼

側面板、M6 的背景任務與 M7 的 MCP server 都只從登錄表拿工具。2026-10-24 拆票時定了**工具逐條登記**：命令都標副作用，但只有明確登記的才是工具。這張先做登錄表本身，加上第一個真的工具，後面每張票只要登記自己的工具。

## 做什麼

先跑 `mattpocock-skills:codebase-design`，定下登錄表的邊界再動手。

1. **一條登記**：工具名、給模型看的說明（英文，進固定的 prompt 前綴）、pydantic 輸入、**結果型別**、需要的角色、怎麼呼叫底下的 service 命令。副作用等級與反向命令直接讀命令的標記，不另寫一份；登記到沒標的命令就紅。
2. **統一拒絕**：各模組自己的例外（`IssueRejectedError`、`PlanRejectedError`…）在登錄表這一層轉成一種拒絕，帶理由碼與「重試 / 交給人 / 放棄」，AI 才分得出下一步。模組的例外不改。
3. **依角色過濾**：給一個使用者的工具清單＝登錄表裡他的角色碰得到的那些，檢查與 API 是同一道（`api/gate.py` 的邏輯，不在模型這邊另做一份）。
4. **actor**：AI 代誰做的要看得出來，AI 活動頁（票 14）要從這裡撈。看現有 `actor: str` 的寫法再定格式，寫進 plan §11.6。
5. **結果型別匯出給前端**：讓前端拿到有型別的結果（走現有的 OpenAPI 產生流程），票 09 依它畫卡。
6. **結果裡沒有帳密**：結果型別不得含 API key、密碼、token 欄位，加一道測試掃全部登記。
7. **第一個工具**：`read` 的「最近入庫」（一段時間內入庫了哪些作品與集），給票 09 的 tracer 用。

## 驗收

- [x] 登記沒標副作用的命令會紅；工具的等級與命令的標記一致（pytest）
- [x] `user` 拿到的工具清單沒有管理員命令，與 API 門禁同一道（pytest）
- [x] 各模組的拒絕例外經登錄表變成統一拒絕，帶下一步（pytest）
- [x] 掃描測試擋下含帳密欄位的結果型別（雙向變異）
- [x] 「最近入庫」可以經登錄表呼叫，結果型別出現在前端的產生型別裡
- [x] 全部檢查、pytest、vitest 綠；plan §11.6、CONTEXT.md、progress.md 已更新

## Comments

- **設計**（codebase-design）：呼叫端只學 `Registry.tools_for(role)` 與 `Registry.invoke(name, arguments, context)`；
  機制在 `services/registry.py`，登記在 `services/tools.py`。「需要的角色」不另寫，**登記寫做同一件事的那一支端點**
  `(方法, 路徑)`，角色照門禁的同一張表（`services/access.py`，從 `api/gate.py` 搬下來，`admits` 兩邊共用）。代價：
  沒有對應端點的命令登記不了——brief §14「API-first」本來就要每個工具有 API 的那一份。
- **actor** 定成 `ai:<user id>`（`jobs.ai_actor`）；既有只認純數字的解析（`claims._user_id`）改用 `jobs.user_of`，
  `ai:7` 仍歸到使用者 7（code-review 抓到）。M6 的背景任務沒有使用者，到時另定。
- **`ToolRefusal`（`unknown_tool`、`invalid_input`）不放 `domain/enums.py`**：那裡的 `*Refusal` 每一個都要一張
  狀態碼表（`TestStatusTables`），這兩種沒有端點；照樣進 OpenAPI，前端拿得到。
- **`recent_imports` 只有管理員**（指著 `GET /weekly`）：一般使用者的版本要先決定他在 Jellyfin 看不到的作品怎麼辦
  （M1.5 的媒體庫權限），票 09 的 tracer 用管理員就夠。
- code-review 已處理：actor 解析、`next_steps` 跨 enum 同值誤配（`JobRefusal.MEDIA_MISSING` 對上
  `RssRefusal.MEDIA_MISSING`，改成連型別一起比，有測試）、巢狀結果型別的過期檢查（`TestToolResults` 改成掃全部 `$defs`）、
  四處還指著 `api/gate.py` 的舊位置、名詞表要避開的「工具清單」。
- code-review 未處理（判斷題）：
  - `REJECTIONS` 只收建構時帶 `reason` 的 15 種；`ReportMissingError`、`ItemNotVisibleError`、`TargetTakenError`
    這類「找不到 / 看不到」的例外會當 bug 丟出去。第一個工具碰不到；之後的票登記會丟它們的命令時再加（並決定 `next`）。
  - `UnclaimedError` 帶 `path` 不帶 `detail`，轉成 `Refusal` 時 `detail` 是空的。
  - `run` 實際呼叫的是不是 `command=` 那一支沒有檢查（「等級與標記一致」那條測試在建構上就成立）。要守得改成
    登錄表替 `run` 呼叫命令，等寫入工具（票 11、12）的形狀出來再看值不值得。
  - `RecentWork` 與 `api/weekly.ImportedWorkOut` 同形：services 不能 import api；`api/weekly` 反過來用 `RecentWork`
    會改掉前端週報頁的型別名，不在這張票做。
  - `(方法, 路徑)` 是裸的 `tuple[str, str]`（門禁的兩張表原本就是），`REJECTIONS` 的 `reason` / `detail` 用
    `getattr` 與一個 `type: ignore` 取（沒有共同基底，票面說模組的例外不改）。
  - 測試裡的 `service_modules()` 與 `test_command_marks` 各一份（從測試模組 import 會帶進它的頂層副作用，同 `tests/endpoints.py` 的理由）。
- 合進 main（cd790065，票 04、07）時兩條紅：票 04 把閘門擴到公開類別上的 async 方法，`Registry.invoke` 沒標——
  標 `irreversible`（派發到每一條登記，照最壞的那一條；要人確認的那一道在對話核心，票 10），`TestTheDispatcherItself`
  寫明理由；票 07 的 `ai.AiRefusedError` 收 `reason`，掃描抓到它不在 `REJECTIONS`——收進去，同形不必特別處理。
  `registry` 因此 import `services.ai`：票 08 的對話核心若放進 `ai`、又要 import 登錄表，會成環，到時把例外或核心拆開。
