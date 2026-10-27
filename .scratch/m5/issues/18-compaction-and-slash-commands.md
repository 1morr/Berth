# 18 — 上下文壓縮與斜線指令

**Status:** done

**Blocked by:** 12

**讀:** plan §11.6〈分段〉第 7 段；brief §20.24 的壓縮那一條；`docs/research/m5-prototype-2026-10-27.md`〈發現〉第 5 點；`docs/research/m5-ai-direction-2026-10-27.md` C2；`scripts/experiments/m5_agent_chat.py` 的 `compact`、`maybe_compact`、`api_command`

## 為什麼

對話一長，成本與錯誤都會變多。壓縮最容易出錯的地方有三個：tool call 和 result 被拆開、待確認的卡片被壓掉、摘要把外部內容裡的指令當成事實。斜線指令要一份登錄表，M7 的 Discord 會共用。

## 做什麼

1. **自動壓縮**：
   - 門檻用 `ctx.context_window_used` 的比例；拿不到時，用上一次回應的 input token 對設定裡的模型 context window。
   - 每輪開頭最多一次。
   - 切點落在使用者訊息上，保留最後兩個回合；被切掉的 tool call 留下的孤兒 tool result 一起拿掉。
2. **摘要的 prompt**：
   - 保留使用者的目標與偏好、確定的 media id 與季集範圍、已送出與已訂閱的、還沒決定的事。
   - 外部內容裡像指令的不寫進摘要。
   - 壓縮本身記一筆 `ai_runs`（種類是壓縮）。
3. **斜線指令登錄表**：
   - `/new`、`/compact`（只留最後一個回合）、`/usage`、`/status`、`/pending`、`/skills`。
   - 只認人類訊息開頭的 `/`；不經過模型（`/compact` 的摘要除外）。
   - 側面板輸入 `/` 時給提示。
4. 待確認的卡片在壓縮之後還在：卡片在 Proposal 表，歷史尾巴的待確認呼叫也保留。

## 驗收

- [x] 壓縮前後 tool call / result 成對、待確認的呼叫在尾巴（測試）
- [x] 有待確認的卡片時 `/compact`，之後照常確認並執行（整合測試）
- [x] 每個斜線指令有測試；側面板的提示實跑過（playwright）
- [x] 全部檢查、pytest、vitest 綠；progress.md 已更新

## Comments

- 2026-10-27 票 17 交接：`/usage` 要顯示網搜次數——伺服器端的是 `ai_runs.web_searches`（各次呼叫在 `ai_calls.web_searches`），Tavily 的是 `ai_tool_calls` 裡 `command = 'web.tavily_search'` 且 `outcome` 是 `ok` / `warned` 的列。費用見票 21 的同一條。
- 2026-10-27 票 19 交接：`/skills` 叫 `skills.list_skills`（讀取、`audience=user`、注入 `role`），回這個人用得上的 skill 名稱與描述；照 skill 的工具過濾過，與 instructions 列的是同一份（`services.skills.skills_for`）。描述是英文（寫給模型的），畫面要不要另外翻由這張決定。
- 2026-10-27 票 18 收尾：驗收第 2 條以 Proposal 層的整合測試做（使用者選定）：`tests/integration/test_agent_slash.py::TestACardSurvivesCompaction` 在票 13 落地前以 `proposals.execute` 代替對話的恢復，交接寫在票 13。側面板的提示與 `/usage`、`/compact` 由 `web/e2e/agent.spec.ts` 的第二條實跑（1280 / 390），截圖在本票資料夾（`slash-hint-*`、`slash-usage-*`、`slash-compacted-*`）。
- 2026-10-27 code-review 沒處理的（都是判斷題）：
  - `Turn` 仍帶著 `provider` / `model_name` / `official` / `secret` 四格（票 11 起就這樣）；`Summarizer` 改成帶整份 `AiEndpoint`，`Turn` 那邊沒跟著收。
  - `run_slash` 每一支指令都先讀一次歷史（順便做擁有者檢查），只有 `/status` 用得到；`/compact` 佔到位子之後自己重讀。
  - 對話 id 的格式與擁有者檢查在 `agent.open_turn` 與 `slash.run_slash` 各寫一份。
  - `run_slash` 整支照最重的 `/compact` 標 `IRREVERSIBLE`，其餘五支是讀取或什麼都不做；要逐支標的話得把它們拆成各自的命令。
  - `services/agent_books.py` 的名字（記帳）要讀 docstring 才知道。
- 2026-10-28 合併 main（票 13 確認卡）：驗收第 2 條的整合測試改成經 `/agent/chat` 的真恢復，搬到 `tests/integration/test_agent_cards.py::TestHistoryShape::test_compact_then_confirm_and_the_resumed_turn_runs_as_usual`（出卡 → `/compact` → 按卡確認 → 恢復那一輪照常執行），取代票 13 那條手動砍掉歷史頭部的模擬，`test_agent_slash.py` 以 `proposals.execute` 代替的那一條刪掉。改壞過確認會紅（`split` 丟掉尾巴最後一則：恢復那一輪找不到待確認的呼叫）。migration `e6b2d9a4c731` 改接在票 13 的 `d8a4f1c6e273` 之後。`/new` 對舊對話卡片照票 13 的現狀（不脫離，`/pending` 看得到）。
