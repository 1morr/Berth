# 17 — 網路搜尋

**Status:** done

**Blocked by:** 11

**讀:** plan §11.6〈已定〉的外部資料；brief §14〈provider〉、§20.24 最後一條；`docs/research/m5-ai-direction-2026-10-27/08-scenario-data-sources.md` §4（各家比較）；`docs/research/m5-prototype-2026-10-27.md`〈兩種接口的差異〉

## 為什麼

推薦新番時要看網路上的評價。provider 走 Anthropic Messages 時（Anthropic 官方，或 DeepSeek 的相容端點），伺服器端的 `web_search` 不用新帳號；Chat Completions 沒有，要另接 Tavily。

## 做什麼

1. provider 是 Anthropic Messages 時，掛伺服器端 `web_search`（pydantic-ai 的 `NativeTool(WebSearchTool(...))`），限制次數，網域預設一份清單。
2. 設了 Tavily key（票 09）時，兩種 provider 都多一個 Tavily 工具（adapter，REST）。外部 MCP client 留到 M7。
3. 搜尋結果是外部內容：標「讀過外部內容」，回覆的引用附網址。
4. 用量：`web_search` 的次數記在 `ai_calls`。Anthropic 官方每次 $0.01；其他端點的價格不知道就不計，畫面說明。

## 驗收

- [x] 兩種 provider 的工具組合正確（有沒有 `web_search`、有沒有 Tavily；測試）
- [x] Tavily adapter 有契約測試（fixture）
- [x] 搜尋次數進 `ai_calls` ~~與 `/usage`~~（測試）——`/usage` 還不存在（票 18），顯示交給票 18，見 Comments
- [x] 全部檢查與 pytest 綠；progress.md 已更新

## Comments

- 2026-10-27 實作（session 紀錄見 progress.md）。code-review 沒處理、留給後面的：
  - **自架的 Anthropic 相容閘道不支援 `web_search` 時每一輪都會出錯**：接口是 Anthropic 就一律掛（DeepSeek 實測支援）。組織在 Console 設了網域允許清單、而 `SEARCH_DOMAINS` 不是它的子集時也是 400。真遇到再加開關（設定 → AI 一個「伺服器端網搜」勾選），或照 400 的原文降級。
  - **Tavily 的次數不在 `ai_calls`**：它是工具呼叫，在 `ai_tool_calls`（`command = 'web.tavily_search'`，`ok` / `warned` 才算搜到）。`ai_runs.web_searches` 只算伺服器端的。票 21 的「網搜次數」要兩邊加，票 18 的 `/usage` 同。
  - `external_texts` 收 Tavily 工具的每一個回傳，連 Berth 自己寫的 `blocked` 與錯誤原文也算進去（比實際讀到的多，不會少）。票 14 比對自由文字參數時若誤判太多再收窄（例如只收帶 `pages` 的）。
  - 「回覆的引用附網址」只靠給模型的指示（`SEARCH_INSTRUCTIONS`），沒有程式檢查；Anthropic 的 `citations` pydantic-ai 沒交出來。票 12 的側面板若要顯示來源再看。
  - 伺服器端搜尋在最後一次模型呼叫最多可能多搜 `web_searches - 1` 次（`max_uses` 固定是為了不讓快取失效，plan §8.8）。
  - 一般使用者也能搜（兩種都是）：見 progress.md 偏差。
