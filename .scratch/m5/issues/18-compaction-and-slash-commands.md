# 18 — 上下文壓縮與斜線指令

**Status:** ready-for-agent

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

- [ ] 壓縮前後 tool call / result 成對、待確認的呼叫在尾巴（測試）
- [ ] 有待確認的卡片時 `/compact`，之後照常確認並執行（整合測試）
- [ ] 每個斜線指令有測試；側面板的提示實跑過（playwright）
- [ ] 全部檢查、pytest、vitest 綠；progress.md 已更新

## Comments

- 2026-10-27 票 17 交接：`/usage` 要顯示網搜次數——伺服器端的是 `ai_runs.web_searches`（各次呼叫在 `ai_calls.web_searches`），Tavily 的是 `ai_tool_calls` 裡 `command = 'web.tavily_search'` 且 `outcome` 是 `ok` / `warned` 的列。費用見票 21 的同一條。
- 2026-10-27 票 19 交接：`/skills` 叫 `skills.list_skills`（讀取、`audience=user`、注入 `role`），回這個人用得上的 skill 名稱與描述；照 skill 的工具過濾過，與 instructions 列的是同一份（`services.skills.skills_for`）。描述是英文（寫給模型的），畫面要不要另外翻由這張決定。
