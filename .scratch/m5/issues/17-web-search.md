# 17 — 網路搜尋

**Status:** ready-for-agent

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

- [ ] 兩種 provider 的工具組合正確（有沒有 `web_search`、有沒有 Tavily；測試）
- [ ] Tavily adapter 有契約測試（fixture）
- [ ] 搜尋次數進 `ai_calls` 與 `/usage`（測試）
- [ ] 全部檢查與 pytest 綠；progress.md 已更新

## Comments
