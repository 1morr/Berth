# 15 — 搜尋工具查得到

**Status:** done

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

- [x] 清掉 Tavily key、再填回：`/status` 當場說得對，下一則訊息的工具清單跟著變（測試）
- [x] 步驟頁看得到這次送出的工具名；舊列顯示「未記錄」（playwright 實跑）
- [x] 全部檢查、pytest、vitest 綠；progress.md 已更新

## Comments

- 2026-11-04 `/status` 與 `open_turn` 共用 `agent.search_tools(settings)`（`web_search` 看接口、`tavily` 看 key），各自判斷就可能說的跟掛的不一樣。`/status` 說的是「下一則訊息」：一輪裡額度用完時伺服器端 `web_search` 會被拿掉，那是這一輪的事，不在 `/status` 說；畫面也寫「下一則訊息」。
- 送出的工具名從 `wrap_model_request` 的 `model_request_parameters` 讀（函式工具給模型的名字 + 伺服器端的 `kind`），動態的 `web_search` 這時已經解好：額度用完那幾次記下的清單沒有它（`TestTheSearchLimit` 守）。出錯的那一次照送出的記，壓縮的摘要記 `[]`（步驟頁寫「沒有」），舊列 `NULL` 寫「未記錄」。
- instructions 那一句多帶「可以用 /status 查」（票只要求「只以當下的清單為準」）：模型被問到工具時有個地方可以指給使用者。
- playwright 實跑（`agent` 情境、範圍外的 port 8611）：`/status` 寫「網路搜尋：伺服器端 web_search」；步驟頁「送出的工具 22 支」展開是 21 支函式工具加 `web_search`；把那一列 `tools_json` 設成 NULL 後寫「未記錄」。
- code-review 已處理：`open_turn` 的 `can_search` / `native_search` 改讀 `search.web_search`（原本另算 `bool(native)`）；`Turn.call_tools` 改名 `sent_tools`；測試改用 `test_agent_slash.in_portal`；清單 key 帶位置；補「出錯那次也記」與「摘要記 `[]`」的斷言。
- code-review 未處理：`web_search` / `tavily` 這一對在 `SearchTools`、`slash.Status`、`StatusOut`、前端各出現一次（Data Clumps）；API 維持平鋪，`slash.Status` 也照其他欄位平鋪，先不包。
