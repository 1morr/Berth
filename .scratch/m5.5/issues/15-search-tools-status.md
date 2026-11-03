# 15 — 搜尋工具查得到

**Status:** ready-for-agent

**Blocked by:** None (can start immediately)

**讀:** spec〈範圍〉「搜尋工具查得到」；brief §20.26（模型誤報工具）；plan §2.6（`ai_calls`）、§6〈agent〉；`docs/research/assistant-feedback-2026-11-01.md`

## 為什麼

正式環境的模型在 Tavily key 已存回之後仍連答兩輪「沒有搜尋工具」。工具清單本來就是每則訊息重建的，問題出在模型的說法，以及事後查不到當時送出了什麼。**不做 reload 指令。**

## 做什麼

1. `/status` 多列這一刻搜得到什麼（伺服器端 `web_search`、Tavily），答案由程式直接給，不經過模型。
2. `_instructions` 加一句：工具可能在兩則訊息之間變動，只以當下的清單為準，不沿用先前的說法。
3. `ai_calls` 新增可為空的 `tools_json`（這次呼叫送出的工具名）；步驟頁顯示，舊列顯示「未記錄」。
4. 文件：plan §2.6。

## 驗收

- [ ] 清掉 Tavily key、再填回：`/status` 當場說得對，下一則訊息的工具清單跟著變（測試）
- [ ] 步驟頁看得到這次送出的工具名；舊列顯示「未記錄」（playwright 實跑）
- [ ] 全部檢查、pytest、vitest 綠；progress.md 已更新
