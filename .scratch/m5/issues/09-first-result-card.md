# 09 — 第一張結果卡：「這週入庫了什麼」（tracer 後半）

**Status:** done

**Blocked by:** 08

**讀:** plan §11.6〈側面板〉與建議票序；CONTEXT.md 的 Result Card；`.scratch/m5/side-panel-shape.md`；`DESIGN.md` 現有的作品卡與海報元件

## 為什麼

這是 M5 的 tracer bullet 終點：側面板問「這週入庫了什麼」，AI 走票 05 登記的 `read` 工具「最近入庫」，回一張作品卡。卡片依命令的結果型別畫，不依模型寫的字；這張把「結果型別 → 卡片」的機制建好，後面每種卡只要加一個元件。

## 做什麼

1. **結果卡的機制**：工具結果帶著結果型別送到前端，前端依型別挑元件，型別來自產生出來的 API 型別（票 05）。認不得的型別有一個安全的退路（只顯示摘要），不壞畫面。
2. **作品卡**：海報、標題、這週入庫的集、在不在媒體庫、連到作品頁（連結走票 02 的同一份路徑）。盡量用現有的作品元件。
3. 模型的文字回覆與卡片並列：文字講重點，細節在卡上，不讓模型把卡的內容再唸一遍（寫在 system 裡）。
4. 歷史對話重整後，卡片照樣畫得出來（結果存在訊息裡，不是重新查）。

## 驗收

- [x] 用假 provider：問「這週入庫了什麼」→ 呼叫「最近入庫」→ 前端畫出作品卡（pytest＋vitest）
- [x] 認不得的結果型別顯示退路，不丟錯（vitest）
- [x] 重整後卡片還在（vitest 或 playwright）
- [x] 真 key 實跑一次（若已有），playwright 截圖附在票上——**沒有真 key，條件不成立**；截圖是演練伺服器（`assistant` 情境）的
- [x] 全部檢查、pytest、vitest 綠；progress.md 已更新

## Comments

- 2026-10-24 實作（session 紀錄在 progress.md）。
- 驗收對照：pytest `tests/integration/test_conversations_api.py::TestResultCards`（假 provider 呼叫「最近入庫」，SSE 的 `tool-output-available` 帶 `RecentImports` 與結果，重讀的 `tool_result` 是同一份）、`test_recent_imports_tool.py`（年份、海報兩輪、收錄狀態；有找不到的整部是 `lost`）、`test_assistant.py`（有工具的 system 說結果在卡上、不唸、拒絕要自己說）、`test_openapi_contract.py`（`ToolResultType` 是登錄表結果型別的封閉集合、產出沒過期）；vitest `AssistantPanel.test.tsx`〈結果卡〉五條（串流時畫、重讀後同一張、重整後照畫且不打 `/api/weekly`、空的、認不得的型別與舊形狀退回摘要）；playwright `assistant.spec.ts`（1280 / 390：問了之後有「最近 7 天入庫」的卡、作品名連到 `/media/…`，重整之後還在）。截圖在本票旁的資料夾 `09-first-result-card/`。
- 變異驗證：`CARDS` 拿掉一格 `tsc` 紅；拿掉 ErrorBoundary，「舊形狀」那條 vitest 紅；`main` 不放 `ToolResultType`，openapi 契約紅。
- 判斷：「在不在媒體庫」解讀成 Jellyfin 收錄了沒（plan §11.6「作品（海報、在不在媒體庫）」），從這段時間的帳本列算（`inventory.imports_presence`），不另外問 Jellyfin。「盡量用現有的作品元件」：面板只有 26rem，牆卡片的 2:3 直格放不下集數與狀態，所以用同一份 `ArtSlot`、`KIND_CODE`、`Dot` 與週報的 `describeSpans` 組成橫放的一列（DESIGN.md〈助理側面板〉的結果卡）。工具名的狀態行留著：它就是退路的那一句摘要。
- code-review 兩軸處理了：CHANGELOG（含票 08 那句「結果卡在下一版」）、development.md 補 `ToolResultType` 的閘門、卡片內距小一號記進 DESIGN.md、`_file_presence` 改回私有、週報與「最近入庫」共用 `_imported_with_rows`（原本兩個同形的迴圈）、卡片文案收進 `assistant.cards.recentImports.presence` 並與作品頁同字（「Jellyfin 已收錄」）、system 那一句限縮成成功的結果並要模型自己說拒絕、DESIGN.md 說清楚只缺幾格的舊結果照畫。
- code-review 沒處理、判斷題：
  - 海報英文那一輪的退路 `poster_url_en or poster_url` 現在有三份（`services/media.py`、`inventory.py`、`weekly.py`）：收成 `MediaSnapshot` 的方法要動另外兩個模組，留給下一次碰到它們的票。
  - `weekly.RecentWork`（dataclass）與 `tools.RecentWork`（pydantic）同名、欄位相近：`tools` import `weekly`，反過來會成環；結果型別要留在登記那一邊。
  - `RecentImportsCard` 的收錄狀態分支與 `InventoryTile` 的那一串相似：牆上那一格找到時是一條 Jellyfin 深連結，不是同一個東西。
  - 演練資料沒有海報與年份，截圖上是「無海報」與「—」；海報畫出來由 vitest 驗（`src` 照 UI 語言挑）。演練伺服器離線，不放外部圖。
- 備份：跑 weekly 的 e2e 蓋掉了 M4 票 131 的兩張截圖，已換回 HEAD 的版本；被蓋的那兩張存在 stash `t09-weekly-131-screenshots-from-e2e-rerun`（不需要時 `git stash drop`）。
